"""
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
import io
import os
import json
import uuid
import threading
import base64
import logging
import time
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
)
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
app.config["SECRET_KEY"] = os.getenv("SECRET_KEY", os.urandom(24).hex())  # For session management
# Enable DEBUG logging for image generation issues
log_level = logging.DEBUG if os.getenv("DEBUG_IMAGE_GEN", "0") == "1" else logging.INFO
logging.basicConfig(level=log_level, format="[%(levelname)s] %(message)s")

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
      .previews { display:grid; grid-template-columns: repeat(auto-fill, minmax(150px,1fr)); gap:10px; margin-top: 16px; }
      .thumb { background:#0f1320; border:1px solid #2a2f3c; border-radius:8px; overflow:hidden; }
      .thumb img { display:block; width:100%; height:auto; }
      .bar { height: 10px; background:#0b1220; border-radius: 9999px; overflow:hidden; border:1px solid #1c2841; }
      .bar > div { height:100%; width:0%; background: linear-gradient(90deg, var(--accent), #8bffd6); transition: width .3s ease; }
      .status { margin-top: 8px; color: var(--muted); font-size: 13px; }
      .ok { color: var(--ok); }
      .auth-section { margin-bottom: 20px; padding-bottom: 20px; border-bottom: 1px solid #2a2f3c; }
      .auth-buttons { display: flex; gap: 10px; flex-wrap: wrap; margin-top: 10px; }
      .auth-btn { background: #2a2f3c; color: var(--fg); padding: 10px 16px; border-radius: 8px; text-decoration: none; border: 1px solid #3a3f4c; font-size: 14px; }
      .auth-btn:hover { background: #3a3f4c; }
      .user-info { color: var(--muted); font-size: 14px; margin-bottom: 10px; }
    </style>
  </head>
  <body>
    <div class="wrap">
      <div class="grid">
        <div class="card">
          <h1>AI Storybook Creator</h1>
          <p class="lead">Upload a child photo, pick gender, and generate a personalized 12‑page 8.5″×8.5″ print‑ready PDF with full bleed. Story is automatically selected: Little Red Riding Hood for girls, Jack and the Beanstalk for boys.</p>

          {% if session and session.get('user_id') %}
          <div class="auth-section">
            <div class="user-info">Logged in as: {{ session.get('name', session.get('email', 'User')) }} | <a href="{{ url_for('dashboard') }}" style="color: var(--accent);">Dashboard</a> | <a href="{{ url_for('logout') }}" style="color: var(--muted);">Logout</a></div>
          </div>
          {% else %}
          <div class="auth-section">
            <label>Login to save your storybooks:</label>
            <div class="auth-buttons">
              {% if oauth and oauth.google %}<a href="{{ url_for('login_google') }}" class="auth-btn">🔵 Login with Google</a>{% endif %}
              {% if oauth and oauth.facebook %}<a href="{{ url_for('login_facebook') }}" class="auth-btn">📘 Login with Facebook</a>{% endif %}
              {% if oauth and oauth.apple %}<a href="{{ url_for('login_apple') }}" class="auth-btn">🍎 Sign in with Apple</a>{% endif %}
            </div>
            <p class="muted" style="margin-top: 10px; font-size: 12px;">You can create storybooks without logging in, but they won't be saved to your account.</p>
          </div>
          {% endif %}

          <form action="{{ url_for('create_story') }}" method="post" enctype="multipart/form-data">
            <label for="child_image">Child photo (JPG/PNG/WEBP, ≤25MB)</label>
            <input type="file" name="child_image" id="child_image" accept="image/*" required />

            <label for="child_name">Child name</label>
            <input type="text" name="child_name" id="child_name" placeholder="Ava" required />

            <fieldset>
              <legend>Gender (required)</legend>
              <label><input type="radio" name="gender" value="female" required /> Girl (Little Red Riding Hood)</label>
              <label><input type="radio" name="gender" value="male" /> Boy (Jack and the Beanstalk)</label>
            </fieldset>

            <button class="btn" type="submit">Generate Story</button>
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

            <h3 style="margin-top:18px;">Preview (updates live)</h3>
            <div class="previews" id="pv"></div>
            <script>
              async function pollPreviews() {
                try {
                  const r = await fetch(`{{ url_for('previews_api', job_id='') }}` + jobId);
                  const j = await r.json();
                  const pv = document.getElementById('pv');
                  pv.innerHTML = '';
                  for (const url of j.previews) {
                    const d = document.createElement('div');
                    d.className = 'thumb';
                    d.innerHTML = `<img src="${url}"/>`;
                    pv.appendChild(d);
                  }
                  if (!j.done) setTimeout(pollPreviews, 1300);
                } catch (e) { setTimeout(pollPreviews, 1700); }
              }
              pollPreviews();
            </script>
          {% else %}
            <h2>Progress</h2>
            <div class="bar"><div style="width:0%"></div></div>
            <div class="status">Submit the form to start. Messages will appear here: “Generating story outline…”, “Creating page 1 of 12…”, etc.</div>
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
        
        if image is None:
            error_msg = f"Failed to generate image for page {page_number} after retries"
            logging.error(f"[thread-{page_idx}] {error_msg}")
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
                    state["message"] = f"Creating pages… {state['completed_pages']}/{total} complete"
                else:
                    state["message"] = "Compiling PDF…"
                
                _write_state(job_id, state)
        
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

def assemble_pdf(pages: List[Image.Image], out_path: str) -> None:
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
    with open(out_path, "wb") as f:
        f.write(buf.getvalue())

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
    pdf_path = os.path.join(OUTPUT_DIR, f"storybook_{job_id}.pdf")
    assemble_pdf(final_images, pdf_path)

    # Step 4: Save book to database if available
    if DB_AVAILABLE and user_id:
        try:
            story_id = get_story_id_by_gender(gender)
            # Store relative path for portability
            pdf_relative_path = f"storybook_{job_id}.pdf"
            book = database.create_book(user_id, story_id, child_name, pdf_relative_path)
            if book:
                logging.info(f"[worker] Book saved to database: book_id={book['book_id']}")
                # Log success
                database.create_log(user_id, "INFO", f"Book created: {child_name}'s {story_id} storybook")
            else:
                logging.warning(f"[worker] Failed to save book to database")
        except Exception as e:
            logging.error(f"[worker] Error saving book to database: {e}")
            if DB_AVAILABLE:
                database.create_log(user_id, "ERROR", f"Failed to save book: {str(e)}")
    else:
        if DB_AVAILABLE:
            database.create_log(None, "INFO", f"Book generated without user: {child_name}'s storybook (job_id={job_id})")

    state["done"] = True
    state["message"] = "Finished"
    _write_state(job_id, state)

# -----------------------------------------------------------------------------
# Routes
# -----------------------------------------------------------------------------
@app.route("/", methods=["GET"])
def index():
    return render_template_string(INDEX_HTML, title=APP_TITLE, session=session, oauth=oauth if OAUTH_AVAILABLE else None)


@app.route("/create", methods=["POST"])
def create_story():
    if "child_image" not in request.files:
        abort(400, "No file part in request")
    file = request.files["child_image"]
    if file.filename == "":
        abort(400, "No file selected")
    if not allowed_file(file.filename):
        abort(400, "Unsupported file type")

    child_name = request.form.get("child_name", "Child").strip()
    gender = request.form.get("gender")
    
    # Get user_id from session (OAuth login)
    user_id = session.get("user_id") if session else None

    if gender not in {"male", "female"}:
        abort(400, "Gender required")

    uid = str(uuid.uuid4())[:8]
    safe_name = secure_filename(file.filename)
    upload_path = os.path.join(UPLOAD_DIR, f"{uid}_{safe_name}")
    file.save(upload_path)

    # Log book creation start
    if DB_AVAILABLE:
        database.create_log(user_id, "INFO", f"Starting storybook generation for {child_name} (gender={gender}, job_id={uid})")

    # Kick off worker thread; UI will poll status
    # Story is automatically determined by gender (lrrh for girl, jatb for boy)
    t = threading.Thread(target=worker_generate, args=(uid, upload_path, child_name, gender, user_id))
    t.daemon = True
    t.start()

    return render_template_string(INDEX_HTML, title=APP_TITLE, job=uid)


@app.route("/status/<job_id>")
def status_api(job_id: str):
    s = _read_state(job_id)
    if not s:
        abort(404)
    # Build the download URL here (we HAVE app/request context).
    if s.get("done"):
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


@app.route("/download/<job_id>")
def download_pdf(job_id: str):
    for fn in os.listdir(OUTPUT_DIR):
        if fn.startswith(f"storybook_{job_id}") and fn.endswith(".pdf"):
            target = os.path.join(OUTPUT_DIR, fn)
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
        token = oauth.google.authorize_access_token() if provider_name == 'google' else \
                oauth.facebook.authorize_access_token() if provider_name == 'facebook' else \
                oauth.apple.authorize_access_token() if provider_name == 'apple' else None
        
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
        
        # Set session
        session['user_id'] = user['user_id']
        session['email'] = user['email']
        session['name'] = user.get('name', name)
        session['oauth_provider'] = provider_name
        
        return redirect(url_for('dashboard'))
        
    except Exception as e:
        logging.error(f"[oauth] Error in {provider_name} callback: {e}")
        abort(500, f"OAuth login failed: {str(e)}")


@app.route("/login/google")
def login_google():
    """Initiate Google OAuth login."""
    if not OAUTH_AVAILABLE or not oauth:
        abort(500, "Google OAuth not configured")
    redirect_uri = url_for('auth_google_callback', _external=True)
    return oauth.google.authorize_redirect(redirect_uri)


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
    redirect_uri = url_for('auth_apple_callback', _external=True)
    return oauth.apple.authorize_redirect(redirect_uri)


@app.route("/auth/apple/callback")
def auth_apple_callback():
    """Handle Apple OAuth callback."""
    return handle_oauth_callback('apple')


@app.route("/logout")
def logout():
    """Logout user and clear session."""
    user_id = session.get('user_id')
    if user_id and DB_AVAILABLE:
        database.create_log(user_id, "INFO", "User logged out")
    session.clear()
    return redirect(url_for('index'))


@app.route("/dashboard")
def dashboard():
    """User dashboard showing their books."""
    user_id = session.get('user_id')
    
    if not user_id:
        return redirect(url_for('index'))
    
    if not DB_AVAILABLE:
        return "Database not available", 500
    
    # Get user info
    user = database.get_user_by_id(user_id)
    if not user:
        session.clear()
        return redirect(url_for('index'))
    
    # Get user's books
    books = database.get_user_books(user_id, limit=50)
    
    # Dashboard HTML
    dashboard_html = f"""
    <!doctype html>
    <html lang="en">
      <head>
        <meta charset="utf-8" />
        <meta name="viewport" content="width=device-width, initial-scale=1" />
        <title>My Dashboard - {APP_TITLE}</title>
        <style>
          :root {{ --bg:#0e0f12; --card:#151821; --fg:#e8ecf1; --muted:#9aa5b1; --accent:#6ee7ff; --ok:#10b981; }}
          body {{ margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; color:var(--fg); background:linear-gradient(180deg, #0e0f12, #0b1020); min-height:100vh; }}
          .wrap {{ max-width: 1200px; margin: 40px auto; padding: 0 16px; }}
          .card {{ background: var(--card); border-radius: 16px; padding: 24px; box-shadow: 0 10px 30px rgba(0,0,0,.35); margin-bottom: 20px; }}
          h1 {{ margin: 0 0 10px; font-size: 28px; }}
          h2 {{ margin: 0 0 20px; font-size: 20px; color: var(--muted); }}
          .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
          .btn {{ display:inline-block; background: var(--accent); color:#001018; padding:12px 16px; border-radius: 9999px; font-weight:600; text-decoration:none; border:none; cursor:pointer; }}
          .btn-secondary {{ background: #2a2f3c; color: var(--fg); }}
          .books-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(250px, 1fr)); gap: 20px; }}
          .book-card {{ background: #0f1320; border: 1px solid #2a2f3c; border-radius: 12px; padding: 16px; }}
          .book-card h3 {{ margin: 0 0 8px; font-size: 18px; }}
          .book-card p {{ margin: 4px 0; color: var(--muted); font-size: 14px; }}
          .empty {{ text-align: center; padding: 40px; color: var(--muted); }}
        </style>
      </head>
      <body>
        <div class="wrap">
          <div class="card">
            <div class="header">
              <div>
                <h1>Welcome, {user.get('name', user.get('email', 'User'))}!</h1>
                <h2>Your Storybooks</h2>
              </div>
              <div>
                <a href="{url_for('index')}" class="btn btn-secondary">Create New Story</a>
                <a href="{url_for('logout')}" class="btn btn-secondary" style="margin-left: 10px;">Logout</a>
              </div>
            </div>
            
            {f'''
            <div class="books-grid">
              {''.join([f'''
              <div class="book-card">
                <h3>{book['child_name']}'s Storybook</h3>
                <p>Story: {book['story_id'].upper()}</p>
                <p>Created: {book['created_at'].strftime('%Y-%m-%d %H:%M') if hasattr(book['created_at'], 'strftime') else book['created_at']}</p>
                <a href="{url_for('download_pdf', job_id=book['pdf_path'].replace('storybook_', '').replace('.pdf', ''))}" class="btn" style="margin-top: 12px; display: inline-block;">Download</a>
              </div>
              ''' for book in books])}
            </div>
            ''' if books else '<div class="empty"><p>No storybooks yet. <a href="' + url_for('index') + '">Create your first one!</a></p></div>')}
          </div>
        </div>
      </body>
    </html>
    """
    
    return render_template_string(dashboard_html)

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
    app.run(debug=True)
