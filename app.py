r"""
AI Storybook Creator — Flask App (Spec‑Aligned v0.1, Online OpenAI Mode)
-----------------------------------------------------------------------
Implements the professor's spec:
- Top‑level form: image upload, story radio, gender radio, submit
- Progress bar + status during generation (per page)
- JSON story outline → 12 page prompts → 12 images via OpenAI (with graceful fallback)
- 8.5″ × 8.5″ + 0.125″ bleed (8.75″) @ 300 DPI → single PDF download
- Consistency: stable prompt; we also embed the page caption into each image for v0.1

Quick start (Windows / PowerShell)
----------------------------------
python -m venv .venv1
.\.venv1\Scripts\Activate.ps1
pip install -r requirements.txt

# Put your key in .env at project root:
# OPENAI_API_KEY=sk-***
# Optional corporate SSL/proxy support:
# REQUESTS_CA_BUNDLE=C:\certs\corp-root.pem
# SSL_CERT_FILE=C:\certs\corp-root.pem
# HTTPS_PROXY=http://user:pass@proxy.host:8080
# (Optional) tuning:
# IMAGE_SIZE=1024x1024
# IMAGE_QUALITY=high
# MODEL_IMAGE=dall-e-3
# MODEL_VISION=gpt-4o

flask run

Open http://127.0.0.1:5000

Folders: ./uploads, ./outputs, ./static/previews, ./runtime (job state)
"""

from __future__ import annotations

# Monkey patch gevent BEFORE importing any other modules (required for gunicorn with gevent workers)
# Gevent is more stable with gunicorn than eventlet
# Only patch if gevent is available - don't use eventlet as it conflicts with Flask context
# IMPORTANT: Prevent eventlet from being imported to avoid conflicts
import sys
if 'eventlet' in sys.modules:
    del sys.modules['eventlet']

try:
    import gevent
    from gevent import monkey
    monkey.patch_all()
    GEVENT_AVAILABLE = True
except ImportError:
    # gevent not available - don't monkey patch, will use threading mode
    GEVENT_AVAILABLE = False
import io
import os
import json
import uuid
import threading
import base64
import logging
import time
from datetime import datetime, timezone
from typing import List, Dict, Any, Optional, Tuple
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
import httpx

# Database module
try:
    import database
    DB_AVAILABLE = True
except ImportError:
    DB_AVAILABLE = False
    logging.warning("[app] Database module not available - running without database")

from flask import (
    Flask,
    render_template_string,
    request,
    url_for,
    send_file,
    abort,
    jsonify,
    session,
    redirect,
    flash,
)
from flask_login import LoginManager, current_user, login_required, login_user
from flask_socketio import SocketIO, emit
from werkzeug.utils import secure_filename

from PIL import Image, ImageDraw, ImageFont
from reportlab.pdfgen import canvas as rl_canvas
from reportlab.lib.utils import ImageReader

# Attempt to import the modern OpenAI SDK
try:
    from openai import OpenAI  # pip install openai>=1.50.0
except Exception:  # graceful if missing
    OpenAI = None  # type: ignore

# -----------------------------------------------------------------------------
# Config (print specs)
# -----------------------------------------------------------------------------
APP_TITLE = "AI Storybook Creator"
BASE_DIR = os.getcwd()
UPLOAD_DIR = os.path.join(BASE_DIR, "uploads")
OUTPUT_DIR = os.path.join(BASE_DIR, "outputs")
PREVIEW_DIR = os.path.join(BASE_DIR, "static", "previews")
RUNTIME_DIR = os.path.join(BASE_DIR, "runtime")  # job json state

TRIM_IN = 8.5
BLEED_IN = 0.125
FULLPAGE_IN = TRIM_IN + (BLEED_IN * 2)  # 8.75 in full‑bleed
DPI = 300
PX = int(FULLPAGE_IN * DPI)  # 2625 px
SAFE_PX = int(0.25 * DPI)
PAGES = 12

ALLOWED_EXTENSIONS = {"png", "jpg", "jpeg", "webp"}

for d in (UPLOAD_DIR, OUTPUT_DIR, PREVIEW_DIR, RUNTIME_DIR):
    os.makedirs(d, exist_ok=True)

# Load .env for API keys and network settings
load_dotenv()

app = Flask(__name__)
app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024

# SECRET_KEY is critical for OAuth - must be fixed, not random
secret_key = os.getenv("SECRET_KEY")
if not secret_key:
    # Generate a random one but warn the user
    import secrets
    secret_key = secrets.token_urlsafe(32)
    logging.warning("[app] SECRET_KEY not set in .env - using random key (OAuth may fail on restart)")
    logging.warning("[app] Add SECRET_KEY to .env for stable OAuth sessions")
else:
    logging.info("[app] SECRET_KEY loaded from .env")
app.config["SECRET_KEY"] = secret_key

# Session configuration for OAuth
app.config["SESSION_COOKIE_SECURE"] = os.getenv("SESSION_COOKIE_SECURE", "False").lower() == "true"  # True for HTTPS only
app.config["SESSION_COOKIE_HTTPONLY"] = True
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"  # Allows OAuth redirects
app.config["PERMANENT_SESSION_LIFETIME"] = 3600  # 1 hour session lifetime
app.config["SESSION_COOKIE_NAME"] = "mystory_session"  # Explicit session cookie name
# CRITICAL: Set cookie domain to None so cookies work for both localhost and 127.0.0.1
app.config["SESSION_COOKIE_DOMAIN"] = None  # None allows cookies to work for both localhost and 127.0.0.1

# Configure SERVER_NAME for url_for() to work in worker threads
# Use localhost by default for better OAuth compatibility (Google prefers localhost over 127.0.0.1)
# NOTE: Setting SERVER_NAME can cause cookie issues - only set if needed
server_name = os.getenv("SERVER_NAME")
if server_name:
    app.config["SERVER_NAME"] = server_name
    logging.info(f"[app] SERVER_NAME set to: {server_name}")
else:
    # Don't set SERVER_NAME by default - let Flask auto-detect
    # This prevents cookie domain issues
    logging.info("[app] SERVER_NAME not set - Flask will auto-detect (recommended for OAuth)")
# Setup comprehensive logging with file rotation and database logging
import logger as app_logger
import logging
LOG_DIR = os.path.join(BASE_DIR, "logs")
app_logger.setup_logging(log_dir=LOG_DIR, max_bytes=10 * 1024 * 1024, backup_count=5)
# Keep standard logging module for compatibility

# Initialize SocketIO for WebSocket support
# Use gevent async mode if available (for gunicorn gevent workers), otherwise use threading
# Don't use eventlet as it conflicts with Flask application context
# Explicitly set async_mode to prevent auto-detection of eventlet
if GEVENT_AVAILABLE:
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*", 
        async_mode='gevent', 
        logger=False, 
        engineio_logger=False,
        allow_upgrades=True,
        ping_timeout=60,
        ping_interval=25
    )
else:
    socketio = SocketIO(
        app, 
        cors_allowed_origins="*", 
        async_mode='threading', 
        logger=False, 
        engineio_logger=False,
        allow_upgrades=True,
        ping_timeout=60,
        ping_interval=25
    )

# Flask-Login setup
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'auth.login'
login_manager.login_message = 'Please log in to access this page.'
login_manager.login_message_category = 'info'

# Load user for Flask-Login
@login_manager.user_loader
def load_user(user_id):
    if DB_AVAILABLE:
        try:
            from auth_routes import load_user as auth_load_user
            return auth_load_user(user_id)
        except Exception as e:
            logging.error(f"[app] Failed to load user: {e}")
    return None

# Register auth blueprint
try:
    from auth_routes import auth_bp, init_limiter, limiter as auth_limiter
    app.register_blueprint(auth_bp, url_prefix='/auth')
    init_limiter(app)
    AUTH_AVAILABLE = True
except ImportError as e:
    AUTH_AVAILABLE = False
    logging.warning(f"[app] Auth routes not available: {e}")
    auth_limiter = None
except Exception as e:
    AUTH_AVAILABLE = False
    logging.warning(f"[app] Failed to initialize auth: {e}")
    auth_limiter = None

# OAuth configuration
try:
    from authlib.integrations.flask_client import OAuth
    oauth = OAuth(app)
    OAUTH_AVAILABLE = True
    
    # Register OAuth providers
    if os.getenv("GOOGLE_CLIENT_ID") and os.getenv("GOOGLE_CLIENT_SECRET"):
        oauth.register(
            name='google',
            client_id=os.getenv("GOOGLE_CLIENT_ID"),
            client_secret=os.getenv("GOOGLE_CLIENT_SECRET"),
            server_metadata_url='https://accounts.google.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email profile'}
        )
    
    if os.getenv("FACEBOOK_CLIENT_ID") and os.getenv("FACEBOOK_CLIENT_SECRET"):
        oauth.register(
            name='facebook',
            client_id=os.getenv("FACEBOOK_CLIENT_ID"),
            client_secret=os.getenv("FACEBOOK_CLIENT_SECRET"),
            access_token_url='https://graph.facebook.com/oauth/access_token',
            access_token_params=None,
            authorize_url='https://www.facebook.com/dialog/oauth',
            authorize_params=None,
            api_base_url='https://graph.facebook.com/',
            client_kwargs={'scope': 'email public_profile'}
        )
    
    if os.getenv("APPLE_CLIENT_ID") and os.getenv("APPLE_CLIENT_SECRET"):
        oauth.register(
            name='apple',
            client_id=os.getenv("APPLE_CLIENT_ID"),
            client_secret=os.getenv("APPLE_CLIENT_SECRET"),
            server_metadata_url='https://appleid.apple.com/.well-known/openid-configuration',
            client_kwargs={'scope': 'openid email name'}
        )
    
    logging.info("[app] OAuth providers configured")
except ImportError:
    OAUTH_AVAILABLE = False
    logging.warning("[app] Authlib not available - OAuth login disabled")
    oauth = None
except Exception as e:
    OAUTH_AVAILABLE = False
    logging.warning(f"[app] OAuth configuration failed: {e}")
    oauth = None

# -----------------------------------------------------------------------------
# HTML (inline)
# -----------------------------------------------------------------------------
INDEX_HTML = r"""
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>{{ title }}</title>
    <style>
      :root { --bg:#0e0f12; --card:#151821; --fg:#e8ecf1; --muted:#9aa5b1; --accent:#6ee7ff; --ok:#10b981; }
      body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; color:var(--fg); background:linear-gradient(180deg, #0e0f12, #0b1020); }
      .wrap { max-width: 960px; margin: 40px auto; padding: 0 16px; }
      .grid { display:grid; grid-template-columns: 1fr; gap: 20px; }
      @media (min-width: 960px) { .grid { grid-template-columns: 460px 1fr; } }
      .card { background: var(--card); border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,.35); }
      h1 { margin: 0 0 10px; font-size: 28px; letter-spacing: .2px; }
      p.lead { color: var(--muted); margin-top: 0; }
      label { display:block; margin: 14px 0 6px; color: var(--muted); }
      input[type="text"], select, input[type="file"] { width:100%; padding:12px 14px; border-radius:10px; border:1px solid #2a2f3c; background:#0f1320; color:var(--fg); }
      fieldset { border:1px solid #2a2f3c; border-radius:12px; padding: 10px 14px; }
      legend { color: var(--muted); padding: 0 6px; }
      .btn { display:inline-block; margin-top:18px; background: var(--accent); color:#001018; padding:12px 16px; border-radius: 9999px; font-weight:600; text-decoration:none; border:none; cursor:pointer; }
      .muted { color:var(--muted); font-size: 12px; }
      .previews { display:grid; grid-template-columns: repeat(4, 1fr); gap:10px; margin-top: 16px; }
      @media (max-width: 768px) { .previews { grid-template-columns: repeat(3, 1fr); } }
      .page-thumb { background:#0f1320; border:2px solid #2a2f3c; border-radius:8px; overflow:hidden; aspect-ratio: 1; position: relative; }
      .page-thumb.loading { border-color: var(--accent); }
      .page-thumb.loading::before { content: ''; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); width: 30px; height: 30px; border: 3px solid #2a2f3c; border-top-color: var(--accent); border-radius: 50%; animation: spin 1s linear infinite; }
      .page-thumb.generated { border-color: var(--ok); }
      .page-thumb.error { border-color: #ef4444; }
      .page-thumb img { display:block; width:100%; height:100%; object-fit: cover; }
      .page-thumb .page-number { position: absolute; top: 4px; left: 4px; background: rgba(0,0,0,0.7); color: var(--fg); padding: 2px 6px; border-radius: 4px; font-size: 11px; font-weight: bold; }
      .page-thumb .error-icon { position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); color: #ef4444; font-size: 24px; }
      @keyframes spin { to { transform: translate(-50%, -50%) rotate(360deg); } }
      .download-btn { display: none; margin-top: 20px; }
      .download-btn.ready { display: inline-block; }
      .bar { height: 10px; background:#0b1220; border-radius: 9999px; overflow:hidden; border:1px solid #1c2841; }
      .bar > div { height:100%; width:0%; background: linear-gradient(90deg, var(--accent), #8bffd6); transition: width .3s ease; }
      .status { margin-top: 8px; color: var(--muted); font-size: 13px; }
      .ok { color: var(--ok); }
      .auth-section { margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #2a2f3c; }
      .auth-buttons { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
      .auth-btn { background: #2a2f3c; color: var(--fg); padding: 10px 16px; border-radius: 8px; text-decoration: none; border: 1px solid #3a3f4c; font-size: 14px; }
      .auth-btn:hover { background: #3a3f4c; }
      .user-info { color: var(--muted); font-size: 14px; margin-bottom: 10px; }
      .btn:disabled { opacity: 0.5; cursor: not-allowed; }
      #story_fieldset label { display: block; margin-bottom: 8px; cursor: pointer; }
      #story_fieldset label:hover { color: var(--accent); }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="grid">
        <div class="card">
          <h1>AI Storybook Creator</h1>
          <p class="lead">Upload a child photo, pick gender, and generate a personalized 12‑page 8.5″×8.5″ print‑ready PDF with full bleed. Story is automatically selected: Little Red Riding Hood for girls, Jack and the Beanstalk for boys.</p>

          {% if current_user and current_user.is_authenticated %}
          <div class="auth-section">
            <div class="user-info">Logged in as: {{ current_user.name or current_user.email }} | <a href="{{ url_for('dashboard') }}" style="color: var(--accent);">Dashboard</a> | <a href="{{ url_for('auth.logout') }}" style="color: var(--muted);">Logout</a></div>
            {% if not current_user.email_verified %}
            <div style="margin-top: 10px; padding: 10px; background: rgba(239, 68, 68, 0.1); border-radius: 8px; color: #ef4444; font-size: 12px;">
              ⚠ Email not verified. <a href="{{ url_for('auth.resend_verification') }}" style="color: var(--accent);">Resend verification email</a>
            </div>
            {% endif %}
          </div>
          {% else %}
          <div class="auth-section">
            <label>Login to save your storybooks:</label>
            <div class="auth-buttons">
              <a href="{{ url_for('auth.login') }}" class="auth-btn">🔐 Login</a>
              <a href="{{ url_for('auth.register') }}" class="auth-btn">📝 Register</a>
              {% if oauth and oauth.google %}<a href="{{ url_for('login_google') }}" class="auth-btn">🔵 Google</a>{% endif %}
              {% if oauth and oauth.facebook %}<a href="{{ url_for('login_facebook') }}" class="auth-btn">📘 Facebook</a>{% endif %}
              {% if oauth and oauth.apple %}<a href="{{ url_for('login_apple') }}" class="auth-btn">🍎 Apple</a>{% endif %}
            </div>
            <p class="muted" style="margin-top: 10px; font-size: 12px;">You can create storybooks without logging in, but they won't be saved to your account.</p>
          </div>
          {% endif %}

          <form action="{{ url_for('create_story') }}" method="post" enctype="multipart/form-data">
            <label for="child_image">Child photo (JPG/PNG/WEBP, ≤25MB)</label>
            {% if image_error %}
            {{ image_error }}
            {% endif %}
            <input type="file" name="child_image" id="child_image" accept="image/*" required />
            <p class="muted" style="margin-top: 4px; font-size: 11px;">Please upload a clear photo with one face visible, good lighting, and appropriate content.</p>

            <label for="child_name">Child name</label>
            {% if name_error %}
            {{ name_error }}
            {% endif %}
            <input type="text" name="child_name" id="child_name" placeholder="Ava" value="{{ child_name_value or '' }}" required />
            <p class="muted" style="margin-top: 4px; font-size: 11px;">Enter a real first name (2-20 letters only)</p>

            <fieldset>
              <legend>Gender (required)</legend>
              <label><input type="radio" name="gender" id="gender_female" value="female" {% if gender_value == 'female' %}checked{% endif %} required onchange="updateStoryOptions()" /> Girl</label>
              <label><input type="radio" name="gender" id="gender_male" value="male" {% if gender_value == 'male' %}checked{% endif %} onchange="updateStoryOptions()" /> Boy</label>
            </fieldset>

            <fieldset id="story_fieldset" style="display: none;">
              <legend>Story (required)</legend>
              <div id="story_options"></div>
            </fieldset>

            <button class="btn" type="submit" id="submit_btn" disabled>Generate Story</button>
            <p class="muted">Specs: 12 pages · 8.5″×8.5″ trim · 0.125″ bleed · 300 DPI · full‑bleed images.</p>
          </form>
        </div>

        <div class="card">
          {% if job %}
            <h2>Status</h2>
            <div class="bar"><div id="pb" style="width:0%"></div></div>
            <div class="status" id="st">Queued…</div>
            <script>
              const jobId = {{ job|tojson }};
              async function poll() {
                try {
                  const r = await fetch(`{{ url_for('status_api', job_id='') }}` + jobId);
                  const j = await r.json();
                  const pct = Math.floor((j.completed_pages / j.total_pages) * 100);
                  document.getElementById('pb').style.width = pct + '%';
                  document.getElementById('st').innerHTML = j.done ? `Finished. <a class="ok" href="${j.download_url}">Download Your Book</a>` : j.message;
                  if (!j.done) setTimeout(poll, 900);
                } catch (e) { setTimeout(poll, 1400); }
              }
              poll();
            </script>

            <h3 style="margin-top:18px;">Pages (Real-Time Preview)</h3>
            <div class="previews" id="pv"></div>
            <a href="#" id="downloadBtn" class="btn download-btn">Download PDF</a>
            <a href="/" class="btn" style="margin-top: 10px; display: inline-block;">Create Another Story</a>
            <script src="https://cdn.socket.io/4.5.4/socket.io.min.js"></script>
            <script>
              const jobId = {{ job|tojson }};
              const totalPages = 12;
              const pages = {};
              
              // Initialize 12 placeholder boxes
              const pv = document.getElementById('pv');
              for (let i = 1; i <= totalPages; i++) {
                const pageDiv = document.createElement('div');
                pageDiv.className = 'page-thumb loading';
                pageDiv.id = `page-${i}`;
                pageDiv.innerHTML = `<div class="page-number">Page ${i}</div>`;
                pv.appendChild(pageDiv);
                pages[i] = { status: 'loading', url: null };
              }
              
              // WebSocket connection with polling fallback
              let socket = null;
              let useWebSocket = false;
              
              // Try to connect via WebSocket
              try {
                socket = io();
                useWebSocket = true;
                
                socket.on('connect', () => {
                  console.log('WebSocket connected');
                  socket.emit('join_job', { job_id: jobId });
                });
                
                socket.on('page_update', (data) => {
                  updatePage(data.page_number, data.status, data.url, data.error);
                });
                
                socket.on('progress_update', (data) => {
                  updateProgress(data.completed, data.total, data.message);
                });
                
                socket.on('job_complete', (data) => {
                  updateProgress(data.total, data.total, 'Finished!');
                  document.getElementById('downloadBtn').href = data.download_url;
                  document.getElementById('downloadBtn').classList.add('ready');
                });
                
                socket.on('disconnect', () => {
                  console.log('WebSocket disconnected, falling back to polling');
                  useWebSocket = false;
                  startPolling();
                });
              } catch (e) {
                console.log('WebSocket not available, using polling fallback');
                useWebSocket = false;
                startPolling();
              }
              
              // Polling fallback
              function startPolling() {
                async function pollStatus() {
                  try {
                    const r = await fetch(`{{ url_for('status_api', job_id='') }}` + jobId);
                    const j = await r.json();
                    updateProgress(j.completed_pages, j.total_pages, j.message);
                    if (j.done) {
                      document.getElementById('downloadBtn').href = j.download_url;
                      document.getElementById('downloadBtn').classList.add('ready');
                      return;
                    }
                    setTimeout(pollStatus, 900);
                  } catch (e) { setTimeout(pollStatus, 1400); }
                }
                
                async function pollPreviews() {
                  try {
                    const r = await fetch(`{{ url_for('previews_api', job_id='') }}` + jobId);
                    const j = await r.json();
                    j.previews.forEach((url, idx) => {
                      const pageNum = idx + 1;
                      if (pages[pageNum].status !== 'generated') {
                        updatePage(pageNum, 'generated', url, null);
                      }
                    });
                    if (!j.done) setTimeout(pollPreviews, 1300);
                  } catch (e) { setTimeout(pollPreviews, 1700); }
                }
                
                pollStatus();
                pollPreviews();
              }
              
              // Update individual page
              function updatePage(pageNum, status, url, error) {
                const pageDiv = document.getElementById(`page-${pageNum}`);
                if (!pageDiv) return;
                
                pages[pageNum] = { status, url, error };
                pageDiv.className = `page-thumb ${status}`;
                
                if (status === 'generated' && url) {
                  pageDiv.innerHTML = `<div class="page-number">Page ${pageNum}</div><img src="${url}" alt="Page ${pageNum}" />`;
                } else if (status === 'error') {
                  pageDiv.innerHTML = `<div class="page-number">Page ${pageNum}</div><div class="error-icon">⚠️</div>`;
                } else {
                  pageDiv.innerHTML = `<div class="page-number">Page ${pageNum}</div>`;
                }
              }
              
              // Update progress bar and status
              function updateProgress(completed, total, message) {
                const pct = Math.floor((completed / total) * 100);
                document.getElementById('pb').style.width = pct + '%';
                document.getElementById('st').innerHTML = message || `Page ${completed}/${total} complete`;
              }
              
              // Start polling if WebSocket failed
              if (!useWebSocket) {
                startPolling();
              }
            </script>
          {% else %}
            <script>
              // Story options by gender
              const storyOptions = {
                female: [{ id: 'lrrh', name: 'Little Red Riding Hood' }],
                male: [{ id: 'jatb', name: 'Jack and the Beanstalk' }]
              };
              
              function updateStoryOptions() {
                const genderRadios = document.querySelectorAll('input[name="gender"]');
                const storyFieldset = document.getElementById('story_fieldset');
                const storyOptionsDiv = document.getElementById('story_options');
                const submitBtn = document.getElementById('submit_btn');
                
                // Find selected gender
                let selectedGender = null;
                for (const radio of genderRadios) {
                  if (radio.checked) {
                    selectedGender = radio.value;
                    break;
                  }
                }
                
                // If gender is selected, show story options
                if (selectedGender) {
                  storyFieldset.style.display = 'block';
                  
                  // Clear existing options
                  storyOptionsDiv.innerHTML = '';
                  
                  // Get stories for selected gender
                  const stories = storyOptions[selectedGender] || [];
                  
                  // Create radio buttons for each story
                  stories.forEach(story => {
                    const label = document.createElement('label');
                    label.style.display = 'block';
                    label.style.marginBottom = '8px';
                    
                    const radio = document.createElement('input');
                    radio.type = 'radio';
                    radio.name = 'story_id';
                    radio.value = story.id;
                    radio.id = `story_${story.id}`;
                    radio.required = true;
                    radio.onchange = checkFormValidity;
                    
                    label.appendChild(radio);
                    label.appendChild(document.createTextNode(` ${story.name}`));
                    storyOptionsDiv.appendChild(label);
                  });
                  
                  // Reset story selection when gender changes
                  checkFormValidity();
                } else {
                  storyFieldset.style.display = 'none';
                  storyOptionsDiv.innerHTML = '';
                  submitBtn.disabled = true;
                }
              }
              
              function checkFormValidity() {
                const genderSelected = document.querySelector('input[name="gender"]:checked');
                const storySelected = document.querySelector('input[name="story_id"]:checked');
                const submitBtn = document.getElementById('submit_btn');
                
                if (genderSelected && storySelected) {
                  submitBtn.disabled = false;
                } else {
                  submitBtn.disabled = true;
                }
              }
              
              // Initialize on page load
              document.addEventListener('DOMContentLoaded', function() {
                // Always reset form state when page loads
                const genderRadios = document.querySelectorAll('input[name="gender"]');
                const storyFieldset = document.getElementById('story_fieldset');
                const storyOptionsDiv = document.getElementById('story_options');
                
                // Clear any previous selections
                genderRadios.forEach(radio => radio.checked = false);
                storyOptionsDiv.innerHTML = '';
                storyFieldset.style.display = 'none';
                
                // Run updateStoryOptions to initialize
                updateStoryOptions();
                
                // Restore story selection if there was a previous value
                {% if story_value %}
                const storyValue = '{{ story_value }}';
                if (storyValue) {
                  setTimeout(() => {
                    const storyRadio = document.getElementById(`story_${storyValue}`);
                    if (storyRadio) {
                      storyRadio.checked = true;
                      checkFormValidity();
                    }
                  }, 100);
                }
                {% endif %}
                
                // Restore gender selection if there was a previous value
                {% if gender_value %}
                const genderValue = '{{ gender_value }}';
                if (genderValue) {
                  const genderRadio = document.getElementById(`gender_${genderValue}`);
                  if (genderRadio) {
                    genderRadio.checked = true;
                    updateStoryOptions();
                    // Restore story selection after a short delay to ensure options are rendered
                    {% if story_value %}
                    setTimeout(() => {
                      const storyValue = '{{ story_value }}';
                      const storyRadio = document.getElementById(`story_${storyValue}`);
                      if (storyRadio) {
                        storyRadio.checked = true;
                        checkFormValidity();
                      }
                    }, 200);
                    {% endif %}
                  }
                }
                {% endif %}
              });
            </script>
            <h2>Progress</h2>
            <div class="bar"><div style="width:0%"></div></div>
            <div class="status">Submit the form to start. Messages will appear here: "Generating story outline…", "Creating page 1 of 12…", etc.</div>
          {% endif %}
        </div>
      </div>
      <footer style="margin: 24px 0 10px; text-align:center; color:#6b7280; font-size: 12px;">Spec‑aligned MVP. This build avoids url_for inside threads. URLs are resolved in /status and /previews routes.</footer>
    </div>
  </body>
</html>
"""

# -----------------------------------------------------------------------------
# Helpers: files, sizing
# -----------------------------------------------------------------------------

def allowed_file(filename: str) -> bool:
    return "." in filename and filename.rsplit(".", 1)[1].lower() in ALLOWED_EXTENSIONS


def square_with_bleed(img: Image.Image, target_px: int = PX) -> Image.Image:
    img = img.convert("RGB")
    w, h = img.size
    scale = min(target_px / w, target_px / h)
    nw, nh = int(w * scale), int(h * scale)
    img_resized = img.resize((nw, nh), Image.LANCZOS)
    canvas_bg = Image.new("RGB", (target_px, target_px), (14, 16, 24))
    paste_xy = ((target_px - nw) // 2, (target_px - nh) // 2)
    canvas_bg.paste(img_resized, paste_xy)
    return canvas_bg

# -----------------------------------------------------------------------------
# Spec: JSON outline generation (Step 1) - Load from vetted config files
# -----------------------------------------------------------------------------

CONFIG_DIR = os.path.join(BASE_DIR, "config")

def load_story_config(story_id: str) -> Dict[str, Any]:
    """Load a story configuration from database (preferred) or config file (fallback).
    
    Args:
        story_id: Story identifier (e.g., "lrrh", "jatb")
    
    Returns:
        Dictionary containing story configuration with story_id, story_name, gender, and pages
    """
    # Try database first if available
    if DB_AVAILABLE:
        try:
            storyline = database.get_storyline(story_id)
            if storyline:
                # Convert database format to config format
                pages_json = storyline["pages_json"]
                return {
                    "story_id": storyline["story_id"],
                    "story_name": storyline["name"],
                    "gender": storyline["gender"],
                    "pages": pages_json.get("pages", [])
                }
        except Exception as e:
            logging.warning(f"[config] Failed to load from database, falling back to config file: {e}")
    
    # Fallback to config file
    config_path = os.path.join(CONFIG_DIR, f"{story_id}.json")
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        logging.error(f"[config] Story config not found: {config_path}")
        raise ValueError(f"Story config not found: {story_id}")
    except json.JSONDecodeError as e:
        logging.error(f"[config] Invalid JSON in {config_path}: {e}")
        raise ValueError(f"Invalid story config: {story_id}")


def get_story_id_by_gender(gender: str) -> str:
    """Determine story_id based on gender.
    
    Args:
        gender: "female" or "male" (or "girl" or "boy")
    
    Returns:
        Story ID: "lrrh" for girl, "jatb" for boy
    """
    gender_lower = gender.lower()
    if gender_lower in {"female", "girl"}:
        return "lrrh"
    elif gender_lower in {"male", "boy"}:
        return "jatb"
    else:
        raise ValueError(f"Invalid gender: {gender}. Must be 'female'/'girl' or 'male'/'boy'")


def ai_generate_story_outline(child_name: str, gender: str) -> Dict[str, Any]:
    """Return a JSON story plan with 12 pages loaded from vetted config files.
    No dynamic generation - all stories are pre-vetted and stored in config files.
    
    Args:
        child_name: Name of the child
        gender: Gender of the child ("female"/"girl" or "male"/"boy")
    
    Returns:
        Dictionary with story_title and pages array
    """
    # Determine story based on gender
    story_id = get_story_id_by_gender(gender)
    
    # Load story config
    story_config = load_story_config(story_id)
    
    # Generate title based on story and child name
    if story_id == "lrrh":
        title = f"{child_name} Riding Hood"
    else:  # jatb
        title = f"Little {child_name} and the Beanstalk"
    
    # Process pages: replace placeholders in text and image_prompt_template
    pages = []
    for page_data in story_config["pages"]:
        # Replace placeholders in text
        text = page_data["text"].replace("{child_name}", child_name).replace("{title}", title)
        
        # Replace placeholders in image_prompt_template
        image_prompt = page_data["image_prompt_template"].replace("{child_name}", child_name).replace("{title}", title)
        
        pages.append({
            "page_number": page_data["page_number"],
            "scene_description": page_data["scene_desc"],
            "text": text,
            "image_prompt": image_prompt,
        })
    
    return {
        "story_id": story_id,
        "story_title": title,
        "story_name": story_config["story_name"],
        "pages": pages
    }

# -----------------------------------------------------------------------------
# ONLINE image generation (OpenAI) with graceful fallback to a simple renderer
# -----------------------------------------------------------------------------

def _make_openai_client():
    """Create an OpenAI client that respects corp SSL certs and proxies."""
    if not OpenAI:
        logging.warning("[openai] OpenAI SDK not available. Install with: pip install openai>=1.50.0")
        return None
    
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        logging.warning("[openai] OPENAI_API_KEY not found in environment. Set it in .env file.")
        return None
    
    # Clean up API key (remove whitespace, newlines, etc.)
    api_key = api_key.strip()
    
    if api_key.startswith("sk-your-key-here") or len(api_key) < 20:
        logging.warning("[openai] OPENAI_API_KEY appears to be a placeholder. Please set a valid API key.")
        return None
    
    # Warn if API key seems unusually long (might have extra characters)
    if len(api_key) > 100:
        logging.warning("[openai] API key is unusually long (%d chars). Typical OpenAI keys are ~50 chars. Check for extra whitespace or characters.", len(api_key))
    
    # Validate API key format
    if not api_key.startswith("sk-"):
        logging.warning("[openai] API key doesn't start with 'sk-'. This might be invalid.")
    
    # Check for common issues
    if "\n" in api_key or "\r" in api_key:
        logging.warning("[openai] API key contains newline characters. Cleaning...")
        api_key = api_key.replace("\n", "").replace("\r", "")
    
    if " " in api_key and not api_key.startswith("sk-"):
        # Might be multiple keys or formatted incorrectly
        logging.warning("[openai] API key contains spaces. Make sure it's a single key.")

    # Handle SSL certificate verification for internet filters/proxies
    # Option 1: Disable SSL verification (NOT RECOMMENDED for production, but may be needed for filters)
    disable_ssl_verify = os.getenv("OPENAI_DISABLE_SSL_VERIFY", "0") == "1"
    
    # Option 2: Use custom certificate bundle (RECOMMENDED)
    verify_path = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE")
    
    proxy_url = os.getenv("HTTPS_PROXY") or os.getenv("HTTP_PROXY")
    timeout_seconds = float(os.getenv("OPENAI_HTTP_TIMEOUT", "120"))
    
    # IMPORTANT: If SSL verification is disabled, we MUST use custom httpx client
    # because the default OpenAI client doesn't support disabling SSL verification
    # Also use custom client if we have a proxy or custom certificate bundle
    force_custom = os.getenv("OPENAI_USE_CUSTOM_HTTPX", "0") == "1"
    use_custom_httpx = disable_ssl_verify or proxy_url or verify_path or force_custom
    
    # Set verify_path for custom client
    if disable_ssl_verify:
        # SSL verification disabled - set to False
        ssl_verify_for_client = False
    elif verify_path:
        # Use custom certificate bundle
        ssl_verify_for_client = verify_path
    else:
        # Use default certificate verification
        ssl_verify_for_client = True
    
    # Try default client first (ONLY if we don't need custom SSL/proxy config)
    if not use_custom_httpx:
        try:
            logging.info("[openai] Using default OpenAI client (simpler, more reliable)")
            openai_client = OpenAI(api_key=api_key, timeout=timeout_seconds)
            logging.info("[openai] ✓ Default client created successfully")
            return openai_client
        except Exception as e:
            logging.warning("[openai] Default client failed: %s", str(e))
            # If it's an SSL error, we'll need custom config
            if "SSL" in str(e) or "certificate" in str(e).lower():
                logging.info("[openai] SSL error detected, will use custom client with SSL handling")
                use_custom_httpx = True
            else:
                return None
    
    # Use custom httpx client for SSL/proxy scenarios
    if use_custom_httpx:
        try:
            # Create timeout configuration
            timeout_config = httpx.Timeout(
                timeout_seconds,
                connect=30.0,
                read=timeout_seconds,
                write=timeout_seconds,
                pool=30.0
            )
            
            # Log SSL verification status
            if disable_ssl_verify:
                logging.warning("[openai] ⚠ SSL verification DISABLED - not secure but may be needed for internet filters")
            
            # Create httpx client with SSL/proxy configuration
            client = httpx.Client(
                verify=ssl_verify_for_client,
                proxy=proxy_url,
                timeout=timeout_config,
                limits=httpx.Limits(max_keepalive_connections=5, max_connections=10),
                follow_redirects=True
            )
            openai_client = OpenAI(api_key=api_key, http_client=client)
            
            # Log client configuration
            ssl_status = "disabled" if disable_ssl_verify else ("custom cert" if verify_path else "default")
            logging.info("[openai] Client initialized with custom httpx (timeout=%ss, proxy=%s, ssl=%s)", 
                        timeout_seconds, "yes" if proxy_url else "no", ssl_status)
            return openai_client
        except Exception as e:
            logging.error("[openai] Custom httpx client failed: %s", str(e))
            import traceback
            logging.debug(traceback.format_exc())
            return None
    
    return None

_openai_client = _make_openai_client()


def _embed_caption_band(img: Image.Image, text: str) -> Image.Image:
    """Embed a dark band + caption into the bitmap to ensure legibility (v0.1 spec)."""
    if not text:
        return img.convert("RGB")
    band_h = int(min(0.22 * PX, 320))
    band_y0 = PX - band_h
    overlay = Image.new("RGBA", (PX, band_h), (0, 0, 0, 110))
    out = img.convert("RGBA")
    out.alpha_composite(overlay, (0, band_y0))

    d = ImageDraw.Draw(out)
    try:
        font = ImageFont.truetype("DejaVuSans.ttf", 36)
    except Exception:
        font = ImageFont.load_default()

    max_w = PX - SAFE_PX * 2
    words = text.split()
    lines, cur = [], []
    for w in words:
        test = " ".join(cur + [w])
        tw = d.textbbox((0, 0), test, font=font)[2]
        if tw <= max_w:
            cur.append(w)
        else:
            lines.append(" ".join(cur))
            cur = [w]
    if cur:
        lines.append(" ".join(cur))

    y = band_y0 + SAFE_PX // 2
    for line in lines[:3]:
        d.text((SAFE_PX, y), line, font=font, fill=(240, 244, 250, 255))
        y += d.textbbox((0, 0), line, font=font)[3] + 6

    return out.convert("RGB")


def _placeholder_render(child_image_path: str, page: Dict[str, Any]) -> Image.Image:
    """Fallback: square‑fit the uploaded photo with a mild color wash + caption band."""
    base = Image.open(child_image_path).convert("RGB")
    base_sq = square_with_bleed(base, PX)
    avg = base_sq.resize((1, 1), Image.BOX).getpixel((0, 0))
    key = tuple(min(255, int(0.7 * c + 40)) for c in avg)
    overlay = Image.new("RGBA", (PX, PX), key + (60,))
    out = base_sq.convert("RGBA")
    out.alpha_composite(overlay)
    out = out.convert("RGB")
    return _embed_caption_band(out, page.get("text", ""))


def _analyze_child_image(child_image_path: str) -> str:
    """Analyze the child's image using OpenAI Vision API to extract features for consistent character generation.
    Returns empty string on failure (graceful degradation)."""
    if not _openai_client:
        logging.info("[vision] Skipping - OpenAI client not available")
        return ""
    
    # Skip Vision API if disabled via env var (useful for testing or if API is down)
    if os.getenv("SKIP_VISION_API", "0") == "1":
        logging.info("[vision] Skipping - SKIP_VISION_API=1")
        return ""
    
    try:
        # Open and convert image to ensure it's in a format the Vision API can handle
        img = Image.open(child_image_path)
        # Convert to RGB if needed (handles RGBA, P, etc.)
        if img.mode != "RGB":
            img = img.convert("RGB")
        
        # Resize if image is very large to reduce API costs and improve speed
        max_size = 1024
        if max(img.size) > max_size:
            img.thumbnail((max_size, max_size), Image.LANCZOS)
        
        # Save to bytes buffer as JPEG
        buffer = io.BytesIO()
        img.save(buffer, format="JPEG", quality=85)
        buffer.seek(0)
        image_data = buffer.read()
        
        # Check image size (Vision API has limits)
        if len(image_data) > 20 * 1024 * 1024:  # 20MB limit
            logging.warning("[vision] Image too large (%d bytes), skipping analysis", len(image_data))
            return ""
        
        # Encode image to base64
        image_b64 = base64.b64encode(image_data).decode('utf-8')
        
        # Use Vision API to analyze the child's appearance with timeout
        model = os.getenv("MODEL_VISION", "gpt-4o-mini")  # Use cheaper mini model by default
        logging.info("[vision] Analyzing child image with %s...", model)
        
        response = _openai_client.chat.completions.create(
            model=model,
            messages=[
                {
                    "role": "user",
                    "content": [
                        {
                            "type": "text",
                            "text": "Describe this child's appearance in detail for creating a consistent animated character: include hair color and style, eye color, skin tone, facial features, age, and any distinctive features. Be specific but concise."
                        },
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": f"data:image/jpeg;base64,{image_b64}"
                            }
                        }
                    ]
                }
            ],
            max_tokens=150,
            timeout=30.0  # 30 second timeout for Vision API
        )
        description = response.choices[0].message.content
        logging.info("[vision] Success: %s", description[:100] if description else "empty")
        return description or ""
    except Exception as e:
        error_type = type(e).__name__
        error_msg = str(e)
        logging.warning("[vision] Failed to analyze child image (%s): %s", error_type, error_msg)
        # Don't log full traceback for connection errors (too verbose)
        if "Connection" not in error_type:
            import traceback
            logging.debug(traceback.format_exc())
        return ""  # Graceful degradation - continue without description


def _generate_image_with_api(child_image_path: str, outline_page: Dict[str, Any], child_name: str, gender: str, child_description: str) -> Image.Image:
    """Generate image using OpenAI API. Raises exceptions on failure.
    
    This is the core API call - exceptions are raised for retry logic.
    """
    # Get SSL verification setting for image downloads
    disable_ssl_verify = os.getenv("OPENAI_DISABLE_SSL_VERIFY", "0") == "1"
    
    scene = outline_page.get("scene_description", "")
    caption = outline_page.get("text", "")
    vetted_prompt_template = outline_page.get("image_prompt", "")
    
    appearance_hint = f" The main character should look exactly like this description: {child_description}" if child_description else ""

    # Use vetted image prompt template from config, enhanced with child appearance for consistency
    if vetted_prompt_template:
        prompt = (
            f"Disney‑inspired, family‑friendly storybook illustration. Square full‑bleed 8.5in (include bleed edges). "
            f"Main character: a {'girl' if gender=='female' else 'boy'} named {child_name}.{appearance_hint} "
            f"The character must have consistent appearance across all pages (same hair color, eye color, facial features). "
            f"{vetted_prompt_template}. Soft painterly textures, clean composition, cinematic lighting, vibrant but cohesive palette. "
            f'Animated, cartoon style, child-friendly illustration. Place this EXACT short caption legibly in‑scene on a tasteful text panel (no typos): "{caption}"'
        )
    else:
        prompt = (
            f"Disney‑inspired, family‑friendly storybook illustration. Square full‑bleed 8.5in (include bleed edges). "
            f"Main character: a {'girl' if gender=='female' else 'boy'} named {child_name}.{appearance_hint} "
            f"The character must have consistent appearance across all pages (same hair color, eye color, facial features). "
            f"Scene: {scene}. Soft painterly textures, clean composition, cinematic lighting, vibrant but cohesive palette. "
            f'Animated, cartoon style, child-friendly illustration. Place this EXACT short caption legibly in‑scene on a tasteful text panel (no typos): "{caption}"'
        )

    if _openai_client is None or os.getenv("FORCE_PLACEHOLDER", "0") == "1":
        raise RuntimeError("OpenAI client not available or FORCE_PLACEHOLDER is set")
    
    logging.info("[image] OpenAI generate → %s", scene)
    
    # Use correct DALL-E 3 model name
    model = os.getenv("MODEL_IMAGE", "dall-e-3")
    size = os.getenv("IMAGE_SIZE", "1024x1024")
    quality_setting = os.getenv("IMAGE_QUALITY", "standard")
    quality = quality_setting if model == "dall-e-3" else None
    n_count = 1 if model == "dall-e-3" else int(os.getenv("IMAGE_N", "1"))
    
    params = {
        "model": model,
        "prompt": prompt,
        "size": size,
        "n": n_count,
    }
    if quality and model == "dall-e-3":
        params["quality"] = quality
    
    # Generate image (returns URL by default for DALL-E 3)
    resp = _openai_client.images.generate(**params, timeout=180.0)
    
    if not hasattr(resp, 'data') or resp.data is None or len(resp.data) == 0:
        raise ValueError("Invalid response from OpenAI API")
    
    image_result = resp.data[0]
    if image_result is None:
        raise ValueError("No image in response")
    
    # Try to get URL or base64 from the response
    img_url = None
    b64_data = None
    
    if hasattr(image_result, 'url'):
        img_url = getattr(image_result, 'url', None)
    if hasattr(image_result, 'b64_json'):
        b64_data = getattr(image_result, 'b64_json', None)
    
    if not img_url and not b64_data:
        raise ValueError("No URL or base64 data in image result")
    
    # Process base64 if available
    if b64_data:
        raw = base64.b64decode(b64_data)
        im = Image.open(io.BytesIO(raw)).convert("RGB")
        if im.size != (PX, PX):
            im = im.resize((PX, PX), Image.LANCZOS)
        return _embed_caption_band(im, caption)
    
    # Download image from URL
    if not img_url:
        raise ValueError("Image URL is None or empty")
    
    import requests
    img_resp = requests.get(img_url, timeout=30, verify=not disable_ssl_verify)
    img_resp.raise_for_status()
    im = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
    
    if im.size != (PX, PX):
        im = im.resize((PX, PX), Image.LANCZOS)
    
    logging.info("[image] ✓ Successfully generated image for: %s", scene)
    return _embed_caption_band(im, caption)


def _generate_image_with_retry(child_image_path: str, outline_page: Dict[str, Any], child_name: str, gender: str, child_description: str, max_retries: int = 3) -> Optional[Image.Image]:
    """Generate image with retry logic and exponential backoff for rate limits.
    
    Args:
        child_image_path: Path to the uploaded child photo
        outline_page: Page data with scene description and text
        child_name: Name of the child
        gender: Gender of the child ('male' or 'female')
        child_description: Pre-analyzed description of the child's appearance
        max_retries: Maximum number of retry attempts
    
    Returns:
        Generated image or None if all retries failed
    """
    for attempt in range(max_retries):
        try:
            return _generate_image_with_api(child_image_path, outline_page, child_name, gender, child_description)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Check if it's a rate limit error
            is_rate_limit = (
                "RateLimit" in error_type or 
                "429" in error_msg or 
                "rate limit" in error_msg.lower()
            )
            
            if is_rate_limit and attempt < max_retries - 1:
                # Exponential backoff: 2^attempt seconds, max 30 seconds
                wait_time = min(2 ** attempt, 30)
                logging.warning(f"[image] Rate limit hit (attempt {attempt + 1}/{max_retries}), waiting {wait_time}s before retry...")
                time.sleep(wait_time)
                continue
            elif attempt < max_retries - 1:
                # For other errors, shorter wait
                wait_time = min(1 * (attempt + 1), 5)
                logging.warning(f"[image] Error on attempt {attempt + 1}/{max_retries}: {error_type}, retrying in {wait_time}s...")
                time.sleep(wait_time)
                continue
            else:
                # Final attempt failed
                logging.error(f"[image] ✗ Failed after {max_retries} attempts: {error_type} - {error_msg}")
                return None
    
    return None


def _generate_single_image_thread(
    page_data: Tuple[int, Dict[str, Any]], 
    child_image_path: str, 
    child_name: str, 
    gender: str, 
    child_description: str,
    job_id: str,
    state_lock: threading.Lock
) -> Tuple[int, Optional[Image.Image], Optional[str]]:
    """Generate a single image in a thread with progress tracking.
    
    Args:
        page_data: Tuple of (page_index, page_dict)
        child_image_path: Path to the uploaded child photo
        child_name: Name of the child
        gender: Gender of the child
        child_description: Pre-analyzed description
        job_id: Job ID for state tracking
        state_lock: Thread lock for state updates
    
    Returns:
        Tuple of (page_index, image, error_message)
    """
    page_idx, page = page_data
    page_number = page.get("page_number", page_idx + 1)
    scene = page.get("scene_description", f"Page {page_number}")
    
    start_time = time.time()
    prompt_used = page.get("image_prompt", "")[:200]  # Truncate for logging
    
    try:
        logging.info(f"[thread-{page_idx}] Starting page {page_number}: {scene}")
        
        # Generate image with retry logic
        image = _generate_image_with_retry(
            child_image_path, 
            page, 
            child_name, 
            gender, 
            child_description,
            max_retries=3
        )
        
        duration = time.time() - start_time
        
        if image is None:
            error_msg = f"Failed to generate image for page {page_number} after retries"
            logging.error(f"[thread-{page_idx}] {error_msg}")
            # Log image generation failure
            import logger as app_logger
            app_logger.log_image_generation(page_number, prompt_used, duration, "error", job_id, error_msg)
            
            # Emit WebSocket event for page error
            try:
                socketio.emit('page_update', {
                    'page_number': page_number,
                    'status': 'error',
                    'url': None,
                    'error': error_msg
                }, room=job_id)
            except Exception as e:
                logging.warning(f"[socket] Failed to emit error update: {e}")
            
            return (page_idx, None, error_msg)
        
        # Save preview
        fn = f"{job_id}_p{page_number:02d}.jpg"
        outp = os.path.join(PREVIEW_DIR, fn)
        image.save(outp, "JPEG", quality=88)
        
        # Update state thread-safely
        with state_lock:
            state = _read_state(job_id)
            if state:
                # Update completed pages count
                completed = state.get("completed_pages", 0)
                state["completed_pages"] = completed + 1
                
                # Update previews list
                previews = state.get("previews", [])
                preview_path = f"previews/{fn}"
                if preview_path not in previews:
                    previews.append(preview_path)
                state["previews"] = previews
                
                # Update message
                total = state.get("total_pages", PAGES)
                remaining = total - state["completed_pages"]
                if remaining > 0:
                    state["message"] = f"Page {state['completed_pages']}/{total} complete"
                else:
                    state["message"] = "Compiling PDF…"
                
                _write_state(job_id, state)
                
                # Emit WebSocket event for page completion (with app context and SERVER_NAME)
                try:
                    with app.app_context():
                        # Use relative URL or construct absolute URL manually to avoid SERVER_NAME requirement
                        preview_url = f"/static/{preview_path}"
                        socketio.emit('page_update', {
                            'page_number': page_number,
                            'status': 'generated',
                            'url': preview_url
                        }, room=job_id)
                        
                        socketio.emit('progress_update', {
                            'completed': state["completed_pages"],
                            'total': total,
                            'message': state["message"]
                        }, room=job_id)
                except Exception as e:
                    logging.warning(f"[socket] Failed to emit page update: {e}")
        
        logging.info(f"[thread-{page_idx}] ✓ Completed page {page_number}")
        return (page_idx, image, None)
        
    except Exception as e:
        error_msg = f"Exception in thread for page {page_number}: {str(e)}"
        logging.error(f"[thread-{page_idx}] {error_msg}")
        import traceback
        logging.debug(traceback.format_exc())
        return (page_idx, None, error_msg)


def ai_generate_page_image(child_image_path: str, outline_page: Dict[str, Any], child_name: str, gender: str, child_description: str = "") -> Image.Image:
    """Generate image with OpenAI; fallback to placeholder on failure.
    
    Args:
        child_image_path: Path to the uploaded child photo
        outline_page: Page data with scene description and text
        child_name: Name of the child
        gender: Gender of the child ('male' or 'female')
        child_description: Optional pre-analyzed description of the child's appearance (for consistency)
    """
    # Get SSL verification setting for image downloads
    disable_ssl_verify = os.getenv("OPENAI_DISABLE_SSL_VERIFY", "0") == "1"
    
    scene = outline_page.get("scene_description", "")
    caption = outline_page.get("text", "")
    vetted_prompt_template = outline_page.get("image_prompt", "")
    
    # Use provided description or analyze if not provided
    if not child_description:
        child_description = _analyze_child_image(child_image_path)
    appearance_hint = f" The main character should look exactly like this description: {child_description}" if child_description else ""

    # Use vetted image prompt template from config, enhanced with child appearance for consistency
    if vetted_prompt_template:
        # Use the vetted prompt as the base, and enhance it with child appearance details
        prompt = (
            f"Disney‑inspired, family‑friendly storybook illustration. Square full‑bleed 8.5in (include bleed edges). "
            f"Main character: a {'girl' if gender=='female' else 'boy'} named {child_name}.{appearance_hint} "
            f"The character must have consistent appearance across all pages (same hair color, eye color, facial features). "
            f"{vetted_prompt_template}. Soft painterly textures, clean composition, cinematic lighting, vibrant but cohesive palette. "
            f'Animated, cartoon style, child-friendly illustration. Place this EXACT short caption legibly in‑scene on a tasteful text panel (no typos): "{caption}"'
        )
    else:
        # Fallback to scene description if vetted prompt not available
        prompt = (
            f"Disney‑inspired, family‑friendly storybook illustration. Square full‑bleed 8.5in (include bleed edges). "
            f"Main character: a {'girl' if gender=='female' else 'boy'} named {child_name}.{appearance_hint} "
            f"The character must have consistent appearance across all pages (same hair color, eye color, facial features). "
            f"Scene: {scene}. Soft painterly textures, clean composition, cinematic lighting, vibrant but cohesive palette. "
            f'Animated, cartoon style, child-friendly illustration. Place this EXACT short caption legibly in‑scene on a tasteful text panel (no typos): "{caption}"'
        )

    if _openai_client is not None and os.getenv("FORCE_PLACEHOLDER", "0") != "1":
        try:
            logging.info("[image] OpenAI generate → %s", scene)
            
            # Use correct DALL-E 3 model name
            model = os.getenv("MODEL_IMAGE", "dall-e-3")
            size = os.getenv("IMAGE_SIZE", "1024x1024")
            # DALL-E 3: "standard" or "hd"; DALL-E 2 doesn't support quality parameter
            quality_setting = os.getenv("IMAGE_QUALITY", "standard")
            # Only include quality for DALL-E 3
            quality = quality_setting if model == "dall-e-3" else None
            
            # DALL-E 3 only supports n=1
            n_count = 1 if model == "dall-e-3" else int(os.getenv("IMAGE_N", "1"))
            
            # Build parameters based on model
            # DALL-E 3 returns URLs by default (more reliable than base64)
            params = {
                "model": model,
                "prompt": prompt,
                "size": size,
                "n": n_count,
            }
            # Only add quality parameter for DALL-E 3
            if quality and model == "dall-e-3":
                params["quality"] = quality
            
            # Generate image (returns URL by default for DALL-E 3)
            resp = _openai_client.images.generate(**params, timeout=180.0)
            
            # Debug: log response structure
            logging.info("[image] Response received, checking structure...")
            if not hasattr(resp, 'data'):
                raise ValueError(f"No 'data' attribute in response. Response type: {type(resp)}, attributes: {dir(resp)}")
            
            if resp.data is None:
                raise ValueError("Response data is None")
            
            if len(resp.data) == 0:
                raise ValueError("Empty image data array returned from OpenAI")
            
            # Get the first image result
            image_result = resp.data[0]
            if image_result is None:
                raise ValueError("First image result is None")
            
            logging.info("[image] Image result type: %s", type(image_result).__name__)
            
            # Try to get URL or base64 from the response
            img_url = None
            b64_data = None
            
            # Check for URL first (DALL-E 3 default)
            if hasattr(image_result, 'url'):
                img_url = getattr(image_result, 'url', None)
                logging.info("[image] Found URL attribute: %s", "present" if img_url else "None")
            
            # Check for base64 (alternative format)
            if hasattr(image_result, 'b64_json'):
                b64_data = getattr(image_result, 'b64_json', None)
                logging.info("[image] Found b64_json attribute: %s", "present" if b64_data else "None")
            
            # Log all available attributes for debugging
            if not img_url and not b64_data:
                available_attrs = [attr for attr in dir(image_result) if not attr.startswith('_')]
                logging.error("[image] No URL or b64_json found. Available attributes: %s", available_attrs)
                # Try to access as dict if it's a dict-like object
                if hasattr(image_result, '__dict__'):
                    logging.error("[image] Image result __dict__: %s", image_result.__dict__)
                raise ValueError(f"No URL or base64 data in image result. Type: {type(image_result)}, Attributes: {available_attrs}")
            
            # Process base64 if available
            if b64_data:
                logging.info("[image] Using base64 data")
                raw = base64.b64decode(b64_data)
                im = Image.open(io.BytesIO(raw)).convert("RGB")
                logging.info("[image] ✓ Successfully decoded base64 image for: %s", scene)
                if im.size != (PX, PX):
                    im = im.resize((PX, PX), Image.LANCZOS)
                return _embed_caption_band(im, caption)
            
            # Download image from URL
            if not img_url:
                raise ValueError("Image URL is None or empty")
            
            import requests
            logging.info("[image] Downloading image from URL: %s", img_url[:50] + "..." if len(img_url) > 50 else img_url)
            img_resp = requests.get(img_url, timeout=30, verify=not disable_ssl_verify)
            img_resp.raise_for_status()
            im = Image.open(io.BytesIO(img_resp.content)).convert("RGB")
            
            # Resize to target size if needed
            if im.size != (PX, PX):
                im = im.resize((PX, PX), Image.LANCZOS)
            logging.info("[image] ✓ Successfully generated image for: %s", scene)
            return _embed_caption_band(im, caption)
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            
            # Provide more helpful error messages
            if "Connection" in error_type or "Connection" in error_msg:
                logging.error("[image] ✗ Connection error - Cannot reach OpenAI API. Check:")
                logging.error("   1. Internet connection")
                logging.error("   2. Firewall/proxy settings (set HTTPS_PROXY in .env if needed)")
                logging.error("   3. Corporate SSL certificates (set REQUESTS_CA_BUNDLE in .env if needed)")
            elif "Authentication" in error_type or "401" in error_msg or "403" in error_msg:
                logging.error("[image] ✗ Authentication error - Check your OPENAI_API_KEY in .env")
            elif "RateLimit" in error_type or "429" in error_msg:
                logging.error("[image] ✗ Rate limit exceeded - Wait a moment and try again")
            elif "InvalidRequest" in error_type or "400" in error_msg:
                logging.error("[image] ✗ Invalid request: %s", error_msg)
            else:
                logging.error("[image] ✗ Failed (%s): %s", error_type, error_msg)
            
            # Log full traceback only in debug mode or for non-connection errors
            if "Connection" not in error_type:
                import traceback
                logging.debug(traceback.format_exc())

    logging.info("[image] Placeholder render → %s", scene)
    return _placeholder_render(child_image_path, outline_page)

# -----------------------------------------------------------------------------
# PDF assembly (Step 3)
# -----------------------------------------------------------------------------

def assemble_pdf(pages: List[Image.Image], out_path: Optional[str] = None) -> bytes:
    """
    Assemble PDF from page images.
    
    Args:
        pages: List of PIL Images
        out_path: Optional path to save PDF. If None, only returns bytes.
    
    Returns:
        PDF data as bytes
    """
    full_pts = int(round(FULLPAGE_IN * 72))  # 8.75 in * 72 = 630 pt
    buf = io.BytesIO()
    c = rl_canvas.Canvas(buf, pagesize=(full_pts, full_pts))
    for im in pages:
        b = io.BytesIO()
        im.save(b, format="JPEG", quality=92)
        b.seek(0)
        c.drawImage(ImageReader(b), 0, 0, width=full_pts, height=full_pts)
        c.showPage()
    c.save()
    pdf_data = buf.getvalue()
    
    # Optionally save to file if path provided
    if out_path:
        with open(out_path, "wb") as f:
            f.write(pdf_data)
    
    return pdf_data

# -----------------------------------------------------------------------------
# Runtime job state (progress bar + messages)
# -----------------------------------------------------------------------------

def _job_state_path(job_id: str) -> str:
    return os.path.join(RUNTIME_DIR, f"{job_id}.json")


def _write_state(job_id: str, data: Dict[str, Any]) -> None:
    with open(_job_state_path(job_id), "w", encoding="utf-8") as f:
        json.dump(data, f)


def _read_state(job_id: str) -> Dict[str, Any]:
    try:
        with open(_job_state_path(job_id), "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        return {}

# -----------------------------------------------------------------------------
# Worker: executes the high‑level process flow (2.1) and updates state
# -----------------------------------------------------------------------------

def worker_generate(job_id: str, upload_path: str, child_name: str, gender: str, user_id: Optional[int] = None):
    state = {
        "job_id": job_id,
        "message": "Loading story outline…",
        "completed_pages": 0,
        "total_pages": PAGES,
        "done": False,
        "previews": [],
    }
    _write_state(job_id, state)

    # Step 1: story outline (JSON) - loaded from vetted config files
    outline = ai_generate_story_outline(child_name, gender)
    
    # Step 1.5: Analyze child's image once for consistent character generation
    state["message"] = "Analyzing child's appearance…"
    _write_state(job_id, state)
    child_description = _analyze_child_image(upload_path)
    
    state["message"] = "Creating all pages in parallel…"
    _write_state(job_id, state)

    # Step 2: Generate all images in parallel with ThreadPoolExecutor
    # Target: Complete in under 2 minutes
    max_workers = min(12, int(os.getenv("MAX_IMAGE_WORKERS", "6")))  # Default 6 concurrent, max 12
    timeout_seconds = 120  # 2 minutes total timeout
    
    images: List[Optional[Image.Image]] = [None] * PAGES
    state_lock = threading.Lock()
    
    # Prepare page data with indices
    page_data_list = [(idx, page) for idx, page in enumerate(outline["pages"])]
    
    start_time = time.time()
    logging.info(f"[worker] Starting parallel image generation with {max_workers} workers, timeout={timeout_seconds}s")
    
    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        # Submit all tasks
        future_to_page = {
            executor.submit(
                _generate_single_image_thread,
                page_data,
                upload_path,
                child_name,
                gender,
                child_description,
                job_id,
                state_lock
            ): page_data[0]
            for page_data in page_data_list
        }
        
        # Process completed tasks as they finish
        completed_count = 0
        failed_count = 0
        
        for future in as_completed(future_to_page, timeout=timeout_seconds):
            page_idx = future_to_page[future]
            try:
                idx, image, error_msg = future.result(timeout=1)
                
                if image is not None:
                    images[idx] = image
                    completed_count += 1
                    logging.info(f"[worker] Page {idx + 1} completed ({completed_count}/{PAGES})")
                else:
                    # Generate placeholder for failed image
                    logging.warning(f"[worker] Page {idx + 1} failed, using placeholder: {error_msg}")
                    page = outline["pages"][idx]
                    placeholder = _placeholder_render(upload_path, page)
                    images[idx] = placeholder
                    
                    # Save placeholder preview
                    page_number = page.get("page_number", idx + 1)
                    fn = f"{job_id}_p{page_number:02d}.jpg"
                    outp = os.path.join(PREVIEW_DIR, fn)
                    placeholder.save(outp, "JPEG", quality=88)
                    
                    # Update state
                    with state_lock:
                        state = _read_state(job_id)
                        if state:
                            state["completed_pages"] = state.get("completed_pages", 0) + 1
                            previews = state.get("previews", [])
                            preview_path = f"previews/{fn}"
                            if preview_path not in previews:
                                previews.append(preview_path)
                            state["previews"] = previews
                            state["message"] = f"Creating pages… {state['completed_pages']}/{PAGES} complete"
                            _write_state(job_id, state)
                    
                    failed_count += 1
                    
            except Exception as e:
                logging.error(f"[worker] Exception processing page {page_idx + 1}: {e}")
                # Use placeholder for this page
                page = outline["pages"][page_idx]
                placeholder = _placeholder_render(upload_path, page)
                images[page_idx] = placeholder
                failed_count += 1
        
        elapsed = time.time() - start_time
        logging.info(f"[worker] Parallel generation completed in {elapsed:.1f}s ({completed_count} succeeded, {failed_count} failed)")
    
    # Ensure all images are present (fill any missing with placeholders)
    for idx, img in enumerate(images):
        if img is None:
            logging.warning(f"[worker] Page {idx + 1} missing, generating placeholder")
            page = outline["pages"][idx]
            placeholder = _placeholder_render(upload_path, page)
            images[idx] = placeholder
            
            # Save placeholder preview
            page_number = page.get("page_number", idx + 1)
            fn = f"{job_id}_p{page_number:02d}.jpg"
            outp = os.path.join(PREVIEW_DIR, fn)
            placeholder.save(outp, "JPEG", quality=88)
            
            # Update state
            with state_lock:
                state = _read_state(job_id)
                if state:
                    state["completed_pages"] = state.get("completed_pages", 0) + 1
                    previews = state.get("previews", [])
                    preview_path = f"previews/{fn}"
                    if preview_path not in previews:
                        previews.append(preview_path)
                    state["previews"] = previews
                    state["message"] = f"Creating pages… {state['completed_pages']}/{PAGES} complete"
                    _write_state(job_id, state)
    
    # Convert to non-optional list for type safety
    final_images: List[Image.Image] = [img for img in images if img is not None]
    if len(final_images) != PAGES:
        logging.error(f"[worker] Only {len(final_images)}/{PAGES} images generated, filling with placeholders")
        final_images = []
        for idx in range(PAGES):
            if images[idx] is not None:
                final_images.append(images[idx])
            else:
                page = outline["pages"][idx]
                final_images.append(_placeholder_render(upload_path, page))

    # Step 3: compile PDF
    pdf_data = assemble_pdf(final_images)
    
    # Step 4: Save book with proper naming and metadata
    story_id = get_story_id_by_gender(gender)
    pdf_relative_path = None
    thumbnail_relative_path = None
    
    if DB_AVAILABLE and user_id:
        try:
            # Import storage utilities
            import storage
            
            # Generate filename: {user_id}_{timestamp}_{story_id}.pdf
            timestamp = int(datetime.now(timezone.utc).timestamp())
            pdf_filename, pdf_relative_path = storage.generate_filename(user_id, story_id)
            
            # Save PDF using storage system
            if storage.STORAGE_TYPE == "local":
                # For local storage, save to user directory
                user_dir = storage.get_user_storage_dir(user_id)
                pdf_full_path = os.path.join(user_dir, pdf_filename)
                with open(pdf_full_path, "wb") as f:
                    f.write(pdf_data)
                logging.info(f"[worker] PDF saved to: {pdf_full_path}")
            else:
                # For cloud storage, use storage.save_pdf
                storage.save_pdf(pdf_data, pdf_relative_path)
            
            # Generate thumbnail from first page
            try:
                thumb_filename, thumbnail_relative_path = storage.generate_thumbnail_path(user_id, story_id, timestamp)
                
                if storage.STORAGE_TYPE == "local":
                    # Create thumbnail from first page image
                    if final_images and len(final_images) > 0:
                        thumbnail = final_images[0].resize((300, 300), Image.LANCZOS)
                        thumb_full_path = os.path.join(BASE_DIR, "static", thumbnail_relative_path)
                        os.makedirs(os.path.dirname(thumb_full_path), exist_ok=True)
                        thumbnail.save(thumb_full_path, "JPEG", quality=85)
                        logging.info(f"[worker] Thumbnail saved to: {thumb_full_path}")
                    else:
                        thumbnail_relative_path = None
                else:
                    # For cloud, would need to upload thumbnail
                    if final_images and len(final_images) > 0:
                        thumbnail = final_images[0].resize((300, 300), Image.LANCZOS)
                        thumb_buf = io.BytesIO()
                        thumbnail.save(thumb_buf, "JPEG", quality=85)
                        # Would upload to cloud storage here
                        thumbnail_relative_path = None  # Placeholder
            except Exception as e:
                logging.warning(f"[worker] Failed to create thumbnail: {e}")
                thumbnail_relative_path = None
            
            # Save book to database with metadata
            book = database.create_book(
                user_id=user_id,
                story_id=story_id,
                child_name=child_name,
                pdf_path=pdf_relative_path,
                thumbnail_path=thumbnail_relative_path
            )
            
            if book:
                logging.info(f"[worker] Book saved to database: book_id={book['book_id']}")
                # Store book_id and pdf_path in state for download URL generation
                state["book_id"] = book['book_id']
                state["pdf_path"] = pdf_relative_path  # Store path for job download route fallback
                _write_state(job_id, state)
                # Log book completion
                import logger as app_logger
                total_duration = time.time() - start_time
                pdf_size = len(pdf_data) if 'pdf_data' in locals() else 0
                app_logger.log_book_completed(book['book_id'], total_duration, pdf_size, user_id)
            else:
                logging.warning(f"[worker] Failed to save book to database")
                # Store PDF path for download even if book save failed
                state["pdf_path"] = pdf_relative_path
                
        except Exception as e:
            logging.error(f"[worker] Error saving book: {e}")
            import traceback
            logging.debug(traceback.format_exc())
            if DB_AVAILABLE:
                database.create_log(user_id, "ERROR", f"Failed to save book: {str(e)}")
    else:
        # Save to temporary location if no user
        temp_pdf_path = os.path.join(OUTPUT_DIR, f"storybook_{job_id}.pdf")
        with open(temp_pdf_path, "wb") as f:
            f.write(pdf_data)
        pdf_relative_path = f"storybook_{job_id}.pdf"
        
        if DB_AVAILABLE:
            database.create_log(None, "INFO", f"Book generated without user: {child_name}'s storybook (job_id={job_id})")

    state["done"] = True
    state["message"] = "Finished"
    # Store PDF path for download if not using database book
    if not (DB_AVAILABLE and user_id):
        state["pdf_path"] = pdf_relative_path
    _write_state(job_id, state)
    
    # Emit WebSocket event for job completion (with app context)
    try:
        with app.app_context():
            # Always use job download route - it can find the PDF via state file
            download_url = url_for('download_pdf', job_id=job_id, _external=True)
            socketio.emit('job_complete', {
                'total': PAGES,
                'download_url': download_url
            }, room=job_id)
    except Exception as e:
        logging.warning(f"[socket] Failed to emit job complete: {e}")

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML, title=APP_TITLE, session=session, oauth=oauth if OAUTH_AVAILABLE else None, child_name_value="", gender_value="")


@app.route("/create", methods=["POST"])
def create_story():
    if "child_image" not in request.files:
        abort(400, "No file part in request")
    file = request.files["child_image"]
    if file.filename == "":
        abort(400, "No file selected")
    if not allowed_file(file.filename):
        abort(400, "Unsupported file type")

    child_name = request.form.get("child_name", "").strip()
    gender = request.form.get("gender")
    story_id = request.form.get("story_id")
    
    # Get user_id from Flask-Login or session (OAuth login) - needed for logging
    user_id = current_user.user_id if current_user.is_authenticated else (session.get("user_id") if session else None)
    
    # Validate child name
    import name_validator
    is_valid, error_message = name_validator.validate_child_name(child_name)
    if not is_valid:
        # Log validation failure
        import logger as app_logger
        app_logger.log_validation_failure("name", error_message, "", user_id)
        # Return to form with error message
        error_html = f"""
        <div style="padding: 12px; background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-radius: 8px; color: #ef4444; margin-bottom: 16px;">
          <strong>Error:</strong> {error_message}
        </div>
        """
        return render_template_string(INDEX_HTML, title=APP_TITLE, name_error=error_html, child_name_value=child_name, gender_value=gender, story_value=story_id or "")
    
    # Sanitize the name (capitalize properly)
    child_name = name_validator.sanitize_child_name(child_name)

    if gender not in {"male", "female"}:
        abort(400, "Gender required")
    
    # Validate story_id matches gender
    if not story_id:
        abort(400, "Story selection required")
    
    expected_story_id = get_story_id_by_gender(gender)
    if story_id != expected_story_id:
        abort(400, f"Story selection does not match gender. Expected {expected_story_id} for {gender}")

    # Save file temporarily for validation
    uid = str(uuid.uuid4())[:8]
    safe_name = secure_filename(file.filename)
    upload_path = os.path.join(UPLOAD_DIR, f"{uid}_{safe_name}")
    file.save(upload_path)
    
    # Validate image
    import image_validator
    img_valid, img_error = image_validator.validate_image(upload_path)
    if not img_valid:
        # Delete the uploaded file
        try:
            os.remove(upload_path)
        except:
            pass
        # Return to form with error message
        error_html = f"""
        <div style="padding: 12px; background: rgba(239, 68, 68, 0.1); border: 1px solid #ef4444; border-radius: 8px; color: #ef4444; margin-bottom: 16px;">
          <strong>Image Error:</strong> {img_error}
        </div>
        """
        return render_template_string(INDEX_HTML, title=APP_TITLE, image_error=error_html, child_name_value=child_name, gender_value=gender, story_value=story_id or "")

    # Log book creation start
    import logger as app_logger
    app_logger.log_book_generation_start(user_id, story_id, child_name, uid)

    # Kick off worker thread; UI will poll status
    # Story is automatically determined by gender (lrrh for girl, jatb for boy)
    t = threading.Thread(target=worker_generate, args=(uid, upload_path, child_name, gender, user_id))
    t.daemon = True
    t.start()

    return render_template_string(INDEX_HTML, title=APP_TITLE, job=uid)


# WebSocket event handlers
@socketio.on('connect')
def handle_connect():
    logging.info("[socket] Client connected")

@socketio.on('disconnect')
def handle_disconnect():
    logging.info("[socket] Client disconnected")

@socketio.on('join_job')
def handle_join_job(data):
    """Client joins a job room to receive updates."""
    job_id = data.get('job_id')
    if job_id:
        from flask_socketio import join_room
        join_room(job_id)
        logging.info(f"[socket] Client joined job room: {job_id}")
        
        # Send current state immediately
        state = _read_state(job_id)
        if state:
            emit('progress_update', {
                'completed': state.get('completed_pages', 0),
                'total': state.get('total_pages', 12),
                'message': state.get('message', 'Starting...')
            })
            
            # Send any existing previews
            previews = state.get('previews', [])
            for idx, preview_path in enumerate(previews):
                page_num = idx + 1
                preview_url = url_for('static', filename=preview_path, _external=True)
                emit('page_update', {
                    'page_number': page_num,
                    'status': 'generated',
                    'url': preview_url
                })
            
            if state.get('done'):
                # Always use job download route - it can find the PDF via state file
                download_url = url_for('download_pdf', job_id=job_id, _external=True)
                emit('job_complete', {
                    'total': state.get('total_pages', 12),
                    'download_url': download_url
                })


@app.route("/status/<job_id>")
def status_api(job_id: str):
    s = _read_state(job_id)
    if not s:
        abort(404)
    # Build the download URL here (we HAVE app/request context).
    if s.get("done"):
        # Always use job download route - it can find the PDF via state file
        s["download_url"] = url_for("download_pdf", job_id=job_id, _external=True)
    return jsonify(s)


@app.route("/previews/<job_id>")
def previews_api(job_id: str):
    s = _read_state(job_id)
    if not s:
        abort(404)
    # Convert stored relative static paths → absolute URLs safely
    previews = [
        url_for("static", filename=p, _external=True) if p.startswith("previews/") else p
        for p in s.get("previews", [])
    ]
    return jsonify({"previews": previews, "done": bool(s.get("done"))})

# Exempt status and previews endpoints from rate limiting (polled frequently during generation)
# This must be done after the routes are defined
try:
    from auth_routes import limiter
    if limiter:
        limiter.exempt(status_api)
        limiter.exempt(previews_api)
except:
    pass


@app.route("/download/<job_id>")
def download_pdf(job_id: str):
    # First check if there's a state file with PDF path
    state = _read_state(job_id)
    if state and state.get("pdf_path"):
        # If PDF path is stored in state, use it
        pdf_path = state["pdf_path"]
        if os.path.isabs(pdf_path):
            target = pdf_path
        else:
            target = os.path.join(OUTPUT_DIR, pdf_path)
        if os.path.exists(target):
            return send_file(target, as_attachment=True, download_name=os.path.basename(target))
    
    # Fallback: look for storybook_{job_id}.pdf in OUTPUT_DIR
    for fn in os.listdir(OUTPUT_DIR):
        if fn.startswith(f"storybook_{job_id}") and fn.endswith(".pdf"):
            target = os.path.join(OUTPUT_DIR, fn)
            return send_file(target, as_attachment=True, download_name=os.path.basename(target))
    
    # Also check user subdirectories (for logged-in users whose books weren't saved to DB)
    for item in os.listdir(OUTPUT_DIR):
        item_path = os.path.join(OUTPUT_DIR, item)
        if os.path.isdir(item_path):
            for fn in os.listdir(item_path):
                if job_id in fn and fn.endswith(".pdf"):
                    target = os.path.join(item_path, fn)
                    return send_file(target, as_attachment=True, download_name=os.path.basename(target))
    
    abort(404)


@app.route("/test-connection")
def test_connection():
    """Test endpoint to diagnose OpenAI API connectivity issues."""
    import socket
    import ssl
    
    api_key = os.getenv("OPENAI_API_KEY", "")
    results = {
        "openai_client_available": _openai_client is not None,
        "api_key_set": bool(api_key),
        "api_key_length": len(api_key),
        "api_key_prefix": api_key[:7] + "..." if len(api_key) > 7 else api_key,
        "api_key_format_valid": api_key.startswith("sk-") if api_key else False,
        "network_tests": {}
    }
    
    # Test DNS resolution
    try:
        socket.gethostbyname("api.openai.com")
        results["network_tests"]["dns"] = "✓ Resolved api.openai.com"
    except Exception as e:
        results["network_tests"]["dns"] = f"✗ DNS failed: {e}"
    
    # Test TCP connection
    try:
        sock = socket.create_connection(("api.openai.com", 443), timeout=10)
        sock.close()
        results["network_tests"]["tcp"] = "✓ TCP connection to api.openai.com:443 successful"
    except Exception as e:
        results["network_tests"]["tcp"] = f"✗ TCP connection failed: {e}"
    
    # Test SSL connection
    try:
        context = ssl.create_default_context()
        with socket.create_connection(("api.openai.com", 443), timeout=10) as sock:
            with context.wrap_socket(sock, server_hostname="api.openai.com") as ssock:
                results["network_tests"]["ssl"] = f"✓ SSL handshake successful (version: {ssock.version()})"
    except Exception as e:
        results["network_tests"]["ssl"] = f"✗ SSL handshake failed: {e}"
    
    # Test HTTP request using requests library directly (bypass httpx)
    # This helps identify if the issue is with httpx or the API key itself
    try:
        import requests
        test_url = "https://api.openai.com/v1/models"
        headers = {
            "Authorization": f"Bearer {api_key}",
            "User-Agent": "Python-requests/Test"
        }
        # Use same SSL verification settings as the main client
        disable_ssl_verify = os.getenv("OPENAI_DISABLE_SSL_VERIFY", "0") == "1"
        if disable_ssl_verify:
            # SSL verification disabled
            verify_path = False
            results["network_tests"]["ssl_verify_disabled"] = True
        else:
            # Use custom certificate bundle or default verification
            verify_path = os.getenv("REQUESTS_CA_BUNDLE") or os.getenv("SSL_CERT_FILE") or True
            results["network_tests"]["ssl_verify_disabled"] = False
        
        resp = requests.get(test_url, headers=headers, timeout=30, verify=verify_path)
        if resp.status_code == 200:
            data = resp.json()
            model_count = len(data.get("data", []))
            results["network_tests"]["http_direct"] = f"✓ Direct HTTP request successful (status {resp.status_code})"
            results["network_tests"]["http_direct_models"] = model_count
            results["network_tests"]["http_direct_sample"] = [m.get("id") for m in data.get("data", [])[:3]]
        elif resp.status_code == 401:
            results["network_tests"]["http_direct"] = f"✗ Authentication failed (401) - API key is invalid"
            results["network_tests"]["http_direct_error"] = resp.text[:200]
        elif resp.status_code == 403:
            results["network_tests"]["http_direct"] = f"✗ Forbidden (403) - API key may not have permissions"
            results["network_tests"]["http_direct_error"] = resp.text[:200]
        else:
            results["network_tests"]["http_direct"] = f"✗ HTTP request failed (status {resp.status_code})"
            results["network_tests"]["http_direct_error"] = resp.text[:500]
    except ImportError:
        results["network_tests"]["http_direct"] = "⚠ requests module not installed (run: pip install requests)"
    except requests.exceptions.SSLError as e:
        error_str = str(e)
        results["network_tests"]["http_direct"] = f"✗ SSL Certificate Error: {error_str[:200]}"
        results["network_tests"]["http_direct_hint"] = "SSL certificate verification failed - likely caused by internet filter/proxy"
        results["network_tests"]["http_direct_solution"] = {
            "option1": "Export your internet filter's certificate and set REQUESTS_CA_BUNDLE in .env",
            "option2": "Temporarily disable SSL verification by setting OPENAI_DISABLE_SSL_VERIFY=1 in .env (NOT SECURE)",
            "see_troubleshooting": "Check TROUBLESHOOTING.md for detailed instructions"
        }
    except requests.exceptions.ConnectionError as e:
        results["network_tests"]["http_direct"] = f"✗ Connection error: {str(e)}"
        results["network_tests"]["http_direct_hint"] = "Cannot connect to api.openai.com - check firewall/proxy"
    except requests.exceptions.Timeout as e:
        results["network_tests"]["http_direct"] = f"✗ Timeout error: {str(e)}"
        results["network_tests"]["http_direct_hint"] = "Request timed out - API might be slow"
    except Exception as e:
        results["network_tests"]["http_direct"] = f"✗ Direct HTTP request failed: {type(e).__name__} - {str(e)}"
        import traceback
        results["network_tests"]["http_direct_traceback"] = traceback.format_exc()[:500]
    
    # Test OpenAI API call if client is available
    if _openai_client:
        try:
            # Simple test call - list models (low cost)
            # Use a longer timeout and catch more specific errors
            response = _openai_client.models.list(timeout=30.0)
            results["network_tests"]["api_call"] = f"✓ API call successful (found {len(response.data)} models)"
            results["network_tests"]["api_call_sample_models"] = [m.id for m in response.data[:3]]
        except Exception as e:
            error_type = type(e).__name__
            error_msg = str(e)
            results["network_tests"]["api_call"] = f"✗ API call failed: {error_type} - {error_msg}"
            
            # Add more details if available
            if hasattr(e, "response"):
                try:
                    results["network_tests"]["api_call_error_details"] = {
                        "status_code": getattr(e.response, "status_code", None),
                        "headers": dict(getattr(e.response, "headers", {})) if hasattr(e.response, "headers") else None,
                        "body": getattr(e.response, "text", "")[:500] if hasattr(e.response, "text") else None
                    }
                except Exception as ex:
                    results["network_tests"]["api_call_error_details"] = f"Could not extract error details: {ex}"
            
            # Check for specific error types
            if "Connection" in error_type:
                results["network_tests"]["api_call_hint"] = "Connection error - check firewall, proxy, or network settings"
            elif "Timeout" in error_type:
                results["network_tests"]["api_call_hint"] = "Timeout error - API might be slow or unreachable"
            elif "Authentication" in error_type or "401" in error_msg or "403" in error_msg:
                results["network_tests"]["api_call_hint"] = "Authentication error - check API key validity"
    else:
        results["network_tests"]["api_call"] = "✗ OpenAI client not available"
    
    # Check which client type was used
    if _openai_client:
        try:
            # Try to determine client type
            http_client = getattr(_openai_client, '_client', None)
            if http_client:
                client_type = type(http_client).__name__
                results["client_info"] = {
                    "type": client_type,
                    "uses_custom_httpx": "httpx" in client_type.lower() or hasattr(http_client, '_transport')
                }
        except:
            pass
    
    # Check proxy settings and SSL configuration
    disable_ssl_verify = os.getenv("OPENAI_DISABLE_SSL_VERIFY", "0") == "1"
    results["proxy_config"] = {
        "https_proxy": os.getenv("HTTPS_PROXY"),
        "http_proxy": os.getenv("HTTP_PROXY"),
        "requests_ca_bundle": os.getenv("REQUESTS_CA_BUNDLE"),
        "ssl_cert_file": os.getenv("SSL_CERT_FILE"),
        "openai_disable_ssl_verify": disable_ssl_verify,
        "ssl_verification_status": "DISABLED" if disable_ssl_verify else "ENABLED"
    }
    
    # Add helpful message if SSL is disabled
    if disable_ssl_verify:
        results["ssl_warning"] = "⚠ SSL verification is DISABLED - connection is not secure but may work with internet filters"
    
    return jsonify(results)

# -----------------------------------------------------------------------------
# OAuth Login Routes
# -----------------------------------------------------------------------------

def handle_oauth_callback(provider_name: str):
    """Handle OAuth callback and create/link user account."""
    if not OAUTH_AVAILABLE or not oauth:
        abort(500, "OAuth not configured")
    
    if not DB_AVAILABLE:
        abort(500, "Database not available")
    
    try:
        # Get the OAuth provider
        provider = getattr(oauth, provider_name, None)
        if not provider:
            abort(400, f"Unknown OAuth provider: {provider_name}")
        
        # Debug session state
        logging.info(f"[oauth] Callback received for {provider_name}")
        logging.info(f"[oauth] Session ID exists: {bool(session.get('_id'))}")
        logging.info(f"[oauth] Session keys: {list(session.keys())}")
        logging.info(f"[oauth] SECRET_KEY set: {bool(app.config.get('SECRET_KEY'))}")
        
        # Try to get access token - this validates the state parameter
        try:
            token = provider.authorize_access_token()
        except Exception as state_error:
            error_msg = str(state_error)
            if "state" in error_msg.lower() or "csrf" in error_msg.lower():
                logging.error(f"[oauth] CSRF state mismatch for {provider_name}: {error_msg}")
                logging.error("[oauth] Session debug info:")
                logging.error(f"  - Session ID: {session.get('_id', 'N/A')}")
                logging.error(f"  - Session keys: {list(session.keys())}")
                logging.error(f"  - SECRET_KEY set: {bool(app.config.get('SECRET_KEY'))}")
                logging.error(f"  - SECRET_KEY length: {len(app.config.get('SECRET_KEY', ''))}")
                logging.error("[oauth] This usually means:")
                logging.error("  1. SECRET_KEY changed between OAuth start and callback")
                logging.error("  2. Session cookies are not being saved")
                logging.error("  3. Browser blocked cookies")
                logging.error("  4. Using different browser/session")
                logging.error("  5. App was restarted between OAuth start and callback")
                return render_template_string("""
                    <html>
                    <head><title>OAuth Error</title></head>
                    <body style="font-family: Arial; padding: 40px; max-width: 600px; margin: 0 auto;">
                        <h2>OAuth Login Error</h2>
                        <p><strong>CSRF State Mismatch</strong></p>
                        <p>This usually happens when:</p>
                        <ul>
                            <li>Your SECRET_KEY changed (check your .env file)</li>
                            <li>Session cookies were cleared or blocked</li>
                            <li>You're using a different browser or incognito mode</li>
                        </ul>
                        <p><strong>Solution:</strong></p>
                        <ol>
                            <li>Make sure SECRET_KEY is set in your .env file</li>
                            <li>Clear your browser cookies for this site</li>
                            <li>Try logging in again</li>
                        </ol>
                        <p><a href="/">← Back to Home</a></p>
                    </body>
                    </html>
                """), 400
            else:
                raise
        
        if not token:
            abort(400, "Failed to get access token")
        
        if not token:
            abort(400, "Failed to get access token")
        
        # Get user info from provider
        if provider_name == 'google':
            resp = oauth.google.get('https://www.googleapis.com/oauth2/v2/userinfo')
            user_info = resp.json()
            email = user_info.get('email')
            name = user_info.get('name')
            oauth_id = user_info.get('id')
        elif provider_name == 'facebook':
            resp = oauth.facebook.get('https://graph.facebook.com/me?fields=id,name,email')
            user_info = resp.json()
            email = user_info.get('email')
            name = user_info.get('name')
            oauth_id = user_info.get('id')
        elif provider_name == 'apple':
            # Apple returns user info in id_token
            from authlib.jose import jwt
            id_token = token.get('id_token')
            if id_token:
                # Decode without verification for basic info (in production, verify the token)
                claims = jwt.decode(id_token, verify=False)
                email = claims.get('email')
                name = claims.get('name', {}).get('fullName') if isinstance(claims.get('name'), dict) else None
                oauth_id = claims.get('sub')
            else:
                abort(400, "No id_token from Apple")
        else:
            abort(400, "Unknown provider")
        
        if not email or not oauth_id:
            abort(400, "Missing required user information")
        
        # Check if user exists by OAuth ID
        existing_user = database.get_user_by_oauth(provider_name, oauth_id)
        
        if existing_user:
            # User exists, log them in
            user = existing_user
        else:
            # Check if email already exists (account linking)
            existing_by_email = database.get_user_by_email(email)
            
            if existing_by_email:
                # Link OAuth account to existing user
                database.link_oauth_account(existing_by_email['user_id'], provider_name, oauth_id)
                user = existing_by_email
                database.create_log(user['user_id'], "INFO", f"OAuth account linked: {provider_name}")
            else:
                # Create new user
                user = database.create_user(email, provider_name, oauth_id, name)
                if not user:
                    abort(500, "Failed to create user")
                database.create_log(user['user_id'], "INFO", f"New user created via {provider_name}")
        
        # Login with Flask-Login
        from auth_routes import User
        login_user(User(user))
        
        # Set session and mark as permanent
        session.permanent = True
        session['user_id'] = user['user_id']
        session['email'] = user['email']
        session['name'] = user.get('name', name)
        session['oauth_provider'] = provider_name
        
        logging.info(f"[oauth] Successfully logged in user: {email} via {provider_name}")
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        logging.error(f"[oauth] Error in {provider_name} callback: {e}")
        abort(500, f"OAuth login failed: {str(e)}")


@app.route("/login/google")
def login_google():
    """Initiate Google OAuth login."""
    if not OAUTH_AVAILABLE or not oauth:
        abort(500, "Google OAuth not configured")
    
    # Use explicit redirect URI to avoid mismatch issues
    # Check if custom redirect URI is set, otherwise use localhost (Google's preferred format)
    custom_redirect = os.getenv("GOOGLE_REDIRECT_URI")
    if custom_redirect:
        redirect_uri = custom_redirect
    else:
        # Default to localhost instead of 127.0.0.1 for better Google OAuth compatibility
        base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:5000")
        redirect_uri = f"{base_url}/auth/google/callback"
    
    # Ensure session is properly configured before OAuth redirect
    # This is critical for state parameter storage
    session.permanent = True
    # Force session to save before redirect
    session.modified = True
    
    # Store a test value to verify session is working
    session['_oauth_test'] = 'test_value'
    
    logging.info(f"[oauth] Initiating Google OAuth - redirect URI: {redirect_uri}")
    logging.info(f"[oauth] Session ID: {session.get('_id', 'new')}, SECRET_KEY set: {bool(app.config.get('SECRET_KEY'))}")
    logging.info(f"[oauth] Session cookie domain: {app.config.get('SESSION_COOKIE_DOMAIN', 'default')}")
    logging.info(f"[oauth] Request host: {request.host}")
    
    try:
        redirect_response = oauth.google.authorize_redirect(redirect_uri)
        # Force session to be saved in the response
        return redirect_response
    except Exception as e:
        logging.error(f"[oauth] Failed to initiate Google OAuth: {e}")
        raise


@app.route("/auth/google/callback")
def auth_google_callback():
    """Handle Google OAuth callback."""
    return handle_oauth_callback('google')


@app.route("/login/facebook")
def login_facebook():
    """Initiate Facebook OAuth login."""
    if not OAUTH_AVAILABLE or not oauth:
        abort(500, "Facebook OAuth not configured")
    redirect_uri = url_for('auth_facebook_callback', _external=True)
    return oauth.facebook.authorize_redirect(redirect_uri)


@app.route("/auth/facebook/callback")
def auth_facebook_callback():
    """Handle Facebook OAuth callback."""
    return handle_oauth_callback('facebook')


@app.route("/login/apple")
def login_apple():
    """Initiate Apple Sign In."""
    if not OAUTH_AVAILABLE or not oauth:
        abort(500, "Apple OAuth not configured")
    
    # Use explicit redirect URI to avoid mismatch issues
    custom_redirect = os.getenv("APPLE_REDIRECT_URI")
    if custom_redirect:
        redirect_uri = custom_redirect
    else:
        # Default to localhost for consistency
        base_url = os.getenv("OAUTH_BASE_URL", "http://localhost:5000")
        redirect_uri = f"{base_url}/auth/apple/callback"
    
    # Ensure session is properly configured before OAuth redirect
    session.permanent = True
    session.modified = True
    session['_oauth_test'] = 'test_value'
    
    logging.info(f"[oauth] Initiating Apple Sign In - redirect URI: {redirect_uri}")
    logging.info(f"[oauth] Session ID: {session.get('_id', 'new')}, SECRET_KEY set: {bool(app.config.get('SECRET_KEY'))}")
    
    try:
        return oauth.apple.authorize_redirect(redirect_uri)
    except Exception as e:
        logging.error(f"[oauth] Failed to initiate Apple Sign In: {e}")
        raise


@app.route("/auth/apple/callback")
def auth_apple_callback():
    """Handle Apple OAuth callback."""
    return handle_oauth_callback('apple')


@app.route("/dashboard")
@login_required
def dashboard():
    """User dashboard showing their books."""
    user_id = current_user.user_id
    
    if not DB_AVAILABLE:
        return "Database not available", 500
    
    # Get user info
    user = database.get_user_by_id(user_id)
    if not user:
        from flask_login import logout_user
        logout_user()
        session.clear()
        return redirect(url_for('index'))
    
    # Get user's books
    books = database.get_user_books(user_id, limit=50)
    
    # Enrich books with story names
    enriched_books = []
    for book in books:
        story_id = book.get("story_id")
        story_name = "Unknown Story"
        if story_id and DB_AVAILABLE:
            storyline = database.get_storyline(story_id)
            if storyline:
                story_name = storyline.get("name", story_id.upper())
        else:
            # Fallback to config file
            try:
                story_config = load_story_config(story_id)
                story_name = story_config.get("story_name", story_id.upper())
            except:
                story_name = story_id.upper() if story_id else "Unknown Story"
        
        # Format date
        date_obj = book.get("generation_date") or book.get("created_at")
        if date_obj:
            if hasattr(date_obj, "strftime"):
                date_str = date_obj.strftime("%Y-%m-%d %H:%M")
            else:
                date_str = str(date_obj)
        else:
            date_str = "Unknown date"
        
        book_copy = dict(book)
        book_copy["story_name"] = story_name
        book_copy["date_str"] = date_str
        enriched_books.append(book_copy)
    
    # Dashboard HTML
    dashboard_html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>My Dashboard - {APP_TITLE}</title>
        <style>
          :root {{ --bg:#0e0f12; --card:#151821; --fg:#e8ecf1; --muted:#9aa5b1; --accent:#6ee7ff; --ok:#10b981; --danger:#ef4444; }}
          body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; color:var(--fg); background:linear-gradient(180deg, #0e0f12, #0b1020); min-height:100vh; }}
          .wrap {{ max-width: 1400px; margin: 40px auto; padding: 0 16px; }}
          .card {{ background: var(--card); border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,.35); margin-bottom: 20px; }}
          h1 {{ margin: 0 0 10px; font-size: 28px; }}
          h2 {{ margin: 0 0 20px; font-size: 20px; color: var(--muted); }}
          .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; flex-wrap: wrap; gap: 10px; }}
          .header-left {{ flex: 1; }}
          .header-right {{ display: flex; gap: 10px; flex-wrap: wrap; }}
          .view-controls {{ display: flex; gap: 8px; margin-bottom: 20px; padding: 8px; background: #0f1320; border-radius: 8px; }}
          .view-btn {{ background: transparent; color: var(--muted); padding: 8px 16px; border-radius: 6px; border: 1px solid #2a2f3c; cursor: pointer; font-size: 14px; }}
          .view-btn.active {{ background: var(--accent); color: #001018; border-color: var(--accent); }}
          .view-btn:hover {{ background: #2a2f3c; }}
          .btn {{ display:inline-block; background: var(--accent); color:#001018; padding:12px 16px; border-radius: 9999px; font-weight:600; text-decoration:none; border:none; cursor:pointer; font-size: 14px; }}
          .btn-secondary {{ background: #2a2f3c; color: var(--fg); }}
          .btn-danger {{ background: var(--danger); color: white; }}
          .btn-small {{ padding: 8px 12px; font-size: 12px; }}
          .books-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(280px, 1fr)); gap: 20px; }}
          .books-list {{ display: flex; flex-direction: column; gap: 16px; }}
          .book-card {{ background: #0f1320; border: 1px solid #2a2f3c; border-radius: 12px; padding: 16px; transition: transform 0.2s, box-shadow 0.2s; }}
          .book-card:hover {{ transform: translateY(-2px); box-shadow: 0 4px 12px rgba(0,0,0,.4); }}
          .book-card.list-view {{ display: flex; gap: 20px; padding: 20px; }}
          .book-card.list-view .book-thumbnail-wrapper {{ flex-shrink: 0; width: 150px; }}
          .book-card.list-view .book-info {{ flex: 1; }}
          .book-card.list-view .book-actions {{ display: flex; flex-direction: column; gap: 8px; justify-content: center; }}
          .book-thumbnail-wrapper {{ position: relative; cursor: pointer; }}
          .book-thumbnail {{ width: 100%; aspect-ratio: 1; object-fit: cover; border-radius: 8px; margin-bottom: 12px; background: #1a1f2e; transition: opacity 0.2s; }}
          .book-thumbnail:hover {{ opacity: 0.8; }}
          .book-thumbnail-wrapper::after {{ content: '👁️ View'; position: absolute; top: 50%; left: 50%; transform: translate(-50%, -50%); background: rgba(0,0,0,0.7); color: white; padding: 8px 12px; border-radius: 6px; opacity: 0; transition: opacity 0.2s; pointer-events: none; font-size: 12px; }}
          .book-thumbnail-wrapper:hover::after {{ opacity: 1; }}
          .book-card h3 {{ margin: 0 0 8px; font-size: 18px; }}
          .book-card p {{ margin: 4px 0; color: var(--muted); font-size: 14px; }}
          .book-meta {{ display: flex; flex-direction: column; gap: 4px; margin-bottom: 12px; }}
          .book-actions {{ display: flex; gap: 8px; flex-wrap: wrap; margin-top: 12px; }}
          .empty {{ text-align: center; padding: 60px 20px; color: var(--muted); }}
          .empty-icon {{ font-size: 64px; margin-bottom: 16px; }}
          .empty h3 {{ color: var(--fg); margin-bottom: 8px; }}
          .empty p {{ margin: 8px 0; }}
          @media (max-width: 768px) {{
            .book-card.list-view {{ flex-direction: column; }}
            .book-card.list-view .book-thumbnail-wrapper {{ width: 100%; }}
            .header {{ flex-direction: column; align-items: flex-start; }}
            .header-right {{ width: 100%; }}
            .header-right .btn {{ flex: 1; text-align: center; }}
          }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="card">
            <div class="header">
              <div class="header-left">
                <h1>Welcome, {user.get('name', user.get('email', 'User'))}!</h1>
                <h2>Your Storybooks ({len(enriched_books)})</h2>
              </div>
              <div class="header-right">
                <a href="{url_for('index')}" class="btn btn-secondary">Create New Story</a>
                <a href="{url_for('admin_logs')}" class="btn btn-secondary">📊 View Logs</a>
                <a href="{url_for('auth.logout')}" class="btn btn-secondary">Logout</a>
              </div>
            </div>
            
            {f'''
            <div class="view-controls">
              <button class="view-btn active" onclick="setView('grid')" id="btn-grid">📊 Grid View</button>
              <button class="view-btn" onclick="setView('list')" id="btn-list">📋 List View</button>
            </div>
            
            <div class="books-grid" id="books-container">
              ''' + ''.join([f'''
              <div class="book-card">
                <div class="book-thumbnail-wrapper" onclick="window.open('{url_for("view_book", book_id=book["book_id"])}', '_blank')">
                  {f'<img src="{url_for("static", filename=book["thumbnail_path"])}" alt="Thumbnail" class="book-thumbnail" />' if book.get("thumbnail_path") else '<div class="book-thumbnail" style="display: flex; align-items: center; justify-content: center; color: var(--muted); font-size: 48px;">📖</div>'}
                </div>
                <h3>{book["child_name"]}\'s Storybook</h3>
                <div class="book-meta">
                  <p><strong>Story:</strong> {book["story_name"]}</p>
                  <p><strong>Created:</strong> {book["date_str"]}</p>
                </div>
                <div class="book-actions">
                  <a href="{url_for("view_book", book_id=book["book_id"])}" target="_blank" class="btn btn-small">👁️ View</a>
                  <a href="{url_for("download_book", book_id=book["book_id"])}" class="btn btn-small">⬇️ Download</a>
                  <form method="POST" action="{url_for("delete_book", book_id=book["book_id"])}" style="display: inline;" onsubmit="return confirm('Are you sure you want to delete this book? This action cannot be undone.');">
                    <button type="submit" class="btn btn-small btn-danger">🗑️ Delete</button>
                  </form>
                </div>
              </div>
              ''' for book in enriched_books]) + '''
            </div>
            ''' if enriched_books else f'''
            <div class="empty">
              <div class="empty-icon">📚</div>
              <h3>No storybooks yet</h3>
              <p>You haven't created any storybooks yet.</p>
              <p><a href="{url_for('index')}" class="btn">Create your first storybook!</a></p>
            </div>
            '''}
          </div>
        </div>
        
        <script>
          function setView(view) {{
            const container = document.getElementById('books-container');
            const btnGrid = document.getElementById('btn-grid');
            const btnList = document.getElementById('btn-list');
            const cards = container.querySelectorAll('.book-card');
            
            if (view === 'list') {{
              container.classList.remove('books-grid');
              container.classList.add('books-list');
              cards.forEach(card => card.classList.add('list-view'));
              btnGrid.classList.remove('active');
              btnList.classList.add('active');
              localStorage.setItem('bookView', 'list');
            }} else {{
              container.classList.remove('books-list');
              container.classList.add('books-grid');
              cards.forEach(card => card.classList.remove('list-view'));
              btnGrid.classList.add('active');
              btnList.classList.remove('active');
              localStorage.setItem('bookView', 'grid');
            }}
          }}
          
          // Restore saved view preference
          const savedView = localStorage.getItem('bookView') || 'grid';
          if (savedView === 'list') {{
            setView('list');
          }}
        </script>
      </body>
    </html>
    """
    
    return render_template_string(dashboard_html)


@app.route("/book/<int:book_id>/download")
@login_required
def download_book(book_id: int):
    """Download a book PDF."""
    user_id = current_user.user_id
    
    if not DB_AVAILABLE:
        abort(500, "Database not available")
    
    # Get book from database
    book = database.get_book(book_id)
    if not book:
        abort(404, "Book not found")
    
    # Verify book belongs to user
    if book.get("user_id") != user_id:
        abort(403, "Access denied")
    
    # Read PDF from storage
    import storage
    pdf_data = storage.read_pdf(book["pdf_path"])
    
    if not pdf_data:
        abort(404, "PDF file not found")
    
    # Generate download filename
    child_name = book.get("child_name", "Storybook")
    story_id = book.get("story_id", "story")
    filename = f"{child_name}_{story_id}.pdf"
    
    from flask import Response
    return Response(
        pdf_data,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
    )


@app.route("/book/<int:book_id>/view")
@login_required
def view_book(book_id: int):
    """View/preview a book PDF in browser."""
    user_id = current_user.user_id
    
    if not DB_AVAILABLE:
        abort(500, "Database not available")
    
    # Get book from database
    book = database.get_book(book_id)
    if not book:
        abort(404, "Book not found")
    
    # Verify book belongs to user
    if book.get("user_id") != user_id:
        abort(403, "Access denied")
    
    # Read PDF from storage
    import storage
    pdf_data = storage.read_pdf(book["pdf_path"])
    
    if not pdf_data:
        abort(404, "PDF file not found")
    
    from flask import Response
    return Response(
        pdf_data,
        mimetype='application/pdf',
        headers={
            'Content-Disposition': 'inline'
        }
    )


@app.route("/book/<int:book_id>/delete", methods=["POST"])
@login_required
def delete_book(book_id: int):
    """Delete a book."""
    user_id = current_user.user_id
    
    if not DB_AVAILABLE:
        abort(500, "Database not available")
    
    # Get book info before deleting (for file cleanup)
    book = database.get_book(book_id)
    if not book:
        abort(404, "Book not found")
    
    # Verify book belongs to user
    if book.get("user_id") != user_id:
        abort(403, "Access denied")
    
    # Delete book from database
    success = database.delete_book(book_id, user_id)
    
    if success:
        # Also try to delete the PDF and thumbnail files
        import storage
        if book.get("pdf_path"):
            storage.delete_pdf(book["pdf_path"])
        if book.get("thumbnail_path"):
            # Thumbnail deletion would need similar implementation
            pass
        
        flash("Book deleted successfully", "success")
        return redirect(url_for('dashboard'))
    else:
        abort(404, "Book not found or access denied")


@app.route("/admin/logs")
@login_required
def admin_logs():
    """Admin page for viewing and filtering logs."""
    # Simple admin check - in production, use proper role-based access
    # For now, allow any logged-in user (you can add admin check later)
    
    if not DB_AVAILABLE:
        return "Database not available", 500
    
    # Get filter parameters
    user_id_filter = request.args.get('user_id', type=int)
    level_filter = request.args.get('level', '')
    start_date = request.args.get('start_date', '')
    end_date = request.args.get('end_date', '')
    search_term = request.args.get('search', '')
    limit = request.args.get('limit', 100, type=int)
    
    # Get logs
    logs = database.get_logs(
        user_id=user_id_filter,
        level=level_filter if level_filter else None,
        limit=limit,
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None,
        search_term=search_term if search_term else None
    )
    
    # Get statistics
    stats = database.get_log_statistics(
        start_date=start_date if start_date else None,
        end_date=end_date if end_date else None
    )
    
    # Admin page HTML
    admin_html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>Logs - {APP_TITLE}</title>
        <style>
          :root {{ --bg:#0e0f12; --card:#151821; --fg:#e8ecf1; --muted:#9aa5b1; --accent:#6ee7ff; --ok:#10b981; --danger:#ef4444; --warning:#f59e0b; }}
          body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; color:var(--fg); background:linear-gradient(180deg, #0e0f12, #0b1020); min-height:100vh; }}
          .wrap {{ max-width: 1400px; margin: 40px auto; padding: 0 16px; }}
          .card {{ background: var(--card); border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,.35); margin-bottom: 20px; }}
          h1 {{ margin: 0 0 10px; font-size: 28px; }}
          h2 {{ margin: 0 0 20px; font-size: 20px; color: var(--muted); }}
          .filters {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; padding: 16px; background: #0f1320; border-radius: 8px; }}
          .filters input, .filters select {{ padding: 8px 12px; border-radius: 6px; border: 1px solid #2a2f3c; background: #151821; color: var(--fg); }}
          .btn {{ display:inline-block; background: var(--accent); color:#001018; padding:8px 16px; border-radius: 6px; font-weight:600; text-decoration:none; border:none; cursor:pointer; }}
          .btn-secondary {{ background: #2a2f3c; color: var(--fg); }}
          .stats {{ display: grid; grid-template-columns: repeat(auto-fit, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }}
          .stat-card {{ background: #0f1320; padding: 16px; border-radius: 8px; border: 1px solid #2a2f3c; }}
          .stat-value {{ font-size: 24px; font-weight: bold; color: var(--accent); }}
          .stat-label {{ font-size: 12px; color: var(--muted); margin-top: 4px; }}
          .logs-table {{ width: 100%; border-collapse: collapse; }}
          .logs-table th, .logs-table td {{ padding: 12px; text-align: left; border-bottom: 1px solid #2a2f3c; }}
          .logs-table th {{ background: #0f1320; color: var(--muted); font-weight: 600; font-size: 12px; text-transform: uppercase; }}
          .logs-table td {{ font-size: 13px; }}
          .level-INFO {{ color: var(--ok); }}
          .level-WARNING {{ color: var(--warning); }}
          .level-ERROR {{ color: var(--danger); }}
          .level-DEBUG {{ color: var(--muted); }}
          .message {{ max-width: 500px; word-wrap: break-word; }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="card">
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px;">
              <div>
                <h1>System Logs</h1>
                <h2>Post-Mortem Analysis</h2>
              </div>
              <div>
                <a href="{url_for('dashboard')}" class="btn btn-secondary">Back to Dashboard</a>
              </div>
            </div>
            
            <div class="stats">
              <div class="stat-card">
                <div class="stat-value">{stats['total_logs']}</div>
                <div class="stat-label">Total Logs</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{stats['level_counts'].get('INFO', 0)}</div>
                <div class="stat-label">INFO</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{stats['level_counts'].get('WARNING', 0)}</div>
                <div class="stat-label">WARNING</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{stats['level_counts'].get('ERROR', 0)}</div>
                <div class="stat-label">ERROR</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{stats['book_stats']['started']}</div>
                <div class="stat-label">Books Started</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{stats['book_stats']['completed']}</div>
                <div class="stat-label">Books Completed</div>
              </div>
              <div class="stat-card">
                <div class="stat-value">{stats['book_stats']['success_rate']}%</div>
                <div class="stat-label">Success Rate</div>
              </div>
            </div>
            
            <form method="GET" action="{url_for('admin_logs')}">
              <div class="filters">
                <input type="number" name="user_id" placeholder="User ID" value="{user_id_filter or ''}" />
                <select name="level">
                  <option value="">All Levels</option>
                  <option value="DEBUG" {'selected' if level_filter == 'DEBUG' else ''}>DEBUG</option>
                  <option value="INFO" {'selected' if level_filter == 'INFO' else ''}>INFO</option>
                  <option value="WARNING" {'selected' if level_filter == 'WARNING' else ''}>WARNING</option>
                  <option value="ERROR" {'selected' if level_filter == 'ERROR' else ''}>ERROR</option>
                </select>
                <input type="date" name="start_date" value="{start_date}" />
                <input type="date" name="end_date" value="{end_date}" />
                <input type="text" name="search" placeholder="Search message..." value="{search_term}" />
                <input type="number" name="limit" placeholder="Limit" value="{limit}" min="1" max="1000" />
                <button type="submit" class="btn">Filter</button>
                <a href="{url_for('admin_logs')}" class="btn btn-secondary">Clear</a>
              </div>
            </form>
            
            <div class="card">
              <h3>Error Frequency (Top 10)</h3>
              <table class="logs-table">
                <thead>
                  <tr>
                    <th>Error Message</th>
                    <th>Count</th>
                  </tr>
                </thead>
                <tbody>
                  {'<tr><td colspan="2">No errors found</td></tr>' if not stats['error_frequency'] else ''.join([f'<tr><td class="message">{error["message"][:200]}</td><td>{error["count"]}</td></tr>' for error in stats['error_frequency']])}
                </tbody>
              </table>
            </div>
            
            <div class="card">
              <h3>Recent Logs ({len(logs)} entries)</h3>
              <table class="logs-table">
                <thead>
                  <tr>
                    <th>Timestamp</th>
                    <th>Level</th>
                    <th>User ID</th>
                    <th>Message</th>
                  </tr>
                </thead>
                <tbody>
                  {'<tr><td colspan="4">No logs found</td></tr>' if not logs else ''.join([f'''
                  <tr>
                    <td>{log['timestamp'].strftime('%Y-%m-%d %H:%M:%S') if hasattr(log.get('timestamp'), 'strftime') else log.get('timestamp')}</td>
                    <td class="level-{log['level']}">{log['level']}</td>
                    <td>{log.get('user_id', 'N/A')}</td>
                    <td class="message">{log['message'][:300]}{'...' if len(log['message']) > 300 else ''}</td>
                  </tr>
                  ''' for log in logs])}
                </tbody>
              </table>
            </div>
          </div>
        </div>
      </body>
    </html>
    """
    
    return render_template_string(admin_html)


# -----------------------------------------------------------------------------
# requirements.txt (reference)
# -----------------------------------------------------------------------------
# Flask>=3.0.0
# Pillow>=10.0.0
# reportlab>=4.0.0
# Werkzeug>=3.0.0
# python-dotenv>=1.0.1
# openai>=1.50.0
# httpx>=0.27.2

if __name__ == "__main__":
    # Check if running in production (Render sets PORT environment variable)
    port = int(os.getenv("PORT", 5000))
    debug = os.getenv("FLASK_DEBUG", "False").lower() == "true"
    host = "0.0.0.0" if port != 5000 else "localhost"  # Use 0.0.0.0 for Render
    
    # Run on localhost (not 127.0.0.1) for OAuth cookie compatibility in development
    # Browsers treat localhost and 127.0.0.1 as different domains
    socketio.run(app, host=host, port=port, debug=debug, allow_unsafe_werkzeug=debug)
