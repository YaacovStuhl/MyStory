"""
Authentication routes for email/password login.
Handles registration, login, email verification, and password reset.
"""

import logging
from datetime import datetime, timedelta
from flask import Blueprint, request, render_template_string, redirect, url_for, flash, session, jsonify
from flask_login import login_user, logout_user, login_required, current_user

# Try to import Flask-Limiter, but make it optional
try:
    from flask_limiter import Limiter
    from flask_limiter.util import get_remote_address
    FLASK_LIMITER_AVAILABLE = True
except ImportError as e:
    logging.warning(f"[auth_routes] Flask-Limiter not available: {e}")
    FLASK_LIMITER_AVAILABLE = False
    Limiter = None
    get_remote_address = None

import database
import auth
from auth import (
    validate_password, hash_password, verify_password,
    validate_email_address, generate_token,
    send_verification_email, send_password_reset_email
)

# Create blueprint
auth_bp = Blueprint('auth', __name__)

# Initialize rate limiter (will be configured in app.py)
limiter = None


def rate_limit(limit_str):
    """Decorator for rate limiting that works even if limiter is None."""
    def decorator(f):
        if limiter:
            return limiter.limit(limit_str)(f)
        return f
    return decorator


def init_limiter(app):
    """Initialize rate limiter with app."""
    global limiter
    if not FLASK_LIMITER_AVAILABLE:
        logging.warning("[auth_routes] Flask-Limiter not available, rate limiting disabled")
        return
    try:
        limiter = Limiter(
            app=app,
            key_func=get_remote_address,
            default_limits=["200 per day", "50 per hour"]
        )
    except Exception as e:
        logging.warning(f"[auth_routes] Failed to initialize Flask-Limiter: {e}")
        limiter = None


# User class for Flask-Login
class User:
    def __init__(self, user_dict):
        self.user_id = user_dict['user_id']
        self.email = user_dict['email']
        self.name = user_dict.get('name')
        self.email_verified = user_dict.get('email_verified', False)
        self.oauth_provider = user_dict.get('oauth_provider')
    
    def is_authenticated(self):
        return True
    
    def is_active(self):
        return True
    
    def is_anonymous(self):
        return False
    
    def get_id(self):
        return str(self.user_id)


def load_user(user_id):
    """Load user for Flask-Login."""
    user_dict = database.get_user_by_id(int(user_id))
    if user_dict:
        return User(user_dict)
    return None


@auth_bp.route('/register', methods=['GET', 'POST'])
@rate_limit("5 per minute")
def register():
    # Rate limiting will be applied via limiter if available
    if limiter:
        limiter.limit("5 per minute")(lambda: None)  # This won't work, need different approach
    """User registration."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        name = request.form.get('name', '').strip()
        
        # Validate email
        is_valid_email, email_error = validate_email_address(email)
        if not is_valid_email:
            flash(f"Invalid email: {email_error}", "error")
            return render_template_string(REGISTER_HTML, error=email_error)
        
        # Validate password
        is_valid_pw, pw_error = validate_password(password)
        if not is_valid_pw:
            flash(f"Password error: {pw_error}", "error")
            return render_template_string(REGISTER_HTML, error=pw_error)
        
        # Check if user already exists
        existing_user = database.get_user_by_email(email)
        if existing_user:
            flash("An account with this email already exists. Please login instead.", "error")
            return render_template_string(REGISTER_HTML, error="Email already registered")
        
        # Hash password
        password_hash = hash_password(password)
        
        # Generate verification token
        verification_token = generate_token()
        verification_expires = datetime.utcnow() + timedelta(hours=24)
        
        # Create user
        user = database.create_user_with_password(
            email=email,
            password_hash=password_hash,
            name=name or email.split('@')[0],
            verification_token=verification_token,
            verification_expires=verification_expires
        )
        
        if user:
            # Send verification email
            send_verification_email(
                email=email,
                name=user.get('name', email),
                token=verification_token
            )
            
            flash("Registration successful! Please check your email to verify your account.", "success")
            database.create_log(user['user_id'], "INFO", f"User registered: {email}")
            return redirect(url_for('auth.login'))
        else:
            flash("Registration failed. Please try again.", "error")
            return render_template_string(REGISTER_HTML, error="Registration failed")
    
    return render_template_string(REGISTER_HTML)


@auth_bp.route('/login', methods=['GET', 'POST'])
@rate_limit("5 per minute")
def login():
    """User login."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        remember = request.form.get('remember') == 'on'
        
        # Get user
        user_dict = database.get_user_by_email(email)
        if not user_dict:
            flash("Invalid email or password.", "error")
            database.create_log(None, "WARNING", f"Failed login attempt: {email}")
            return render_template_string(LOGIN_HTML, error="Invalid credentials")
        
        # Check if user has password (not OAuth-only)
        if not user_dict.get('password_hash'):
            flash("This account uses OAuth login. Please use Google/Facebook/Apple login instead.", "error")
            return render_template_string(LOGIN_HTML, error="OAuth account")
        
        # Verify password
        if not verify_password(user_dict['password_hash'], password):
            flash("Invalid email or password.", "error")
            database.create_log(None, "WARNING", f"Failed login attempt: {email}")
            return render_template_string(LOGIN_HTML, error="Invalid credentials")
        
        # Create user object for Flask-Login
        user = User(user_dict)
        
        # Login user
        login_user(user, remember=remember)
        
        # Update session
        session['user_id'] = user.user_id
        session['email'] = user.email
        session['name'] = user.name
        session['email_verified'] = user.email_verified
        
        flash(f"Welcome back, {user.name or user.email}!", "success")
        # Use enhanced logger
        import logger as app_logger
        app_logger.log_user_login(user.user_id, None)
        
        # Redirect to dashboard or next page
        next_page = request.args.get('next')
        return redirect(next_page or url_for('dashboard'))
    
    return render_template_string(LOGIN_HTML)


@auth_bp.route('/logout')
@login_required
def logout():
    """User logout."""
    user_id = current_user.user_id
    database.create_log(user_id, "INFO", "User logged out")
    logout_user()
    session.clear()
    flash("You have been logged out.", "info")
    return redirect(url_for('index'))


@auth_bp.route('/verify-email/<token>')
def verify_email(token):
    """Verify email address with token."""
    user_dict = database.get_user_by_verification_token(token)
    
    if not user_dict:
        flash("Invalid or expired verification link.", "error")
        return redirect(url_for('index'))
    
    # Update user verification status
    database.update_user_verification(user_dict['user_id'], verified=True)
    
    flash("Email verified successfully! You can now use all features.", "success")
    database.create_log(user_dict['user_id'], "INFO", "Email verified")
    
    # Auto-login if not already logged in
    if not current_user.is_authenticated:
        user = User(user_dict)
        login_user(user)
        session['user_id'] = user.user_id
        session['email'] = user.email
        session['name'] = user.name
        session['email_verified'] = True
    
    return redirect(url_for('dashboard'))


@auth_bp.route('/resend-verification', methods=['POST'])
@login_required
def resend_verification():
    """Resend verification email."""
    if current_user.email_verified:
        flash("Your email is already verified.", "info")
        return redirect(url_for('dashboard'))
    
    user_dict = database.get_user_by_id(current_user.user_id)
    if not user_dict:
        flash("User not found.", "error")
        return redirect(url_for('index'))
    
    # Generate new token
    verification_token = generate_token()
    verification_expires = datetime.utcnow() + timedelta(hours=24)
    
    database.set_verification_token(
        current_user.user_id,
        verification_token,
        verification_expires
    )
    
    send_verification_email(
        email=current_user.email,
        name=user_dict.get('name', current_user.email),
        token=verification_token
    )
    
    flash("Verification email sent! Please check your inbox.", "success")
    return redirect(url_for('dashboard'))


@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
@rate_limit("3 per hour")
def forgot_password():
    """Request password reset."""
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        
        user_dict = database.get_user_by_email(email)
        if user_dict and user_dict.get('password_hash'):
            # Generate reset token
            reset_token = generate_token()
            reset_expires = datetime.utcnow() + timedelta(hours=1)
            
            database.set_password_reset_token(
                user_dict['user_id'],
                reset_token,
                reset_expires
            )
            
            send_password_reset_email(
                email=email,
                name=user_dict.get('name', email),
                token=reset_token
            )
            
            flash("If an account exists with that email, a password reset link has been sent.", "info")
            database.create_log(user_dict['user_id'], "INFO", "Password reset requested")
        else:
            # Don't reveal if email exists (security best practice)
            flash("If an account exists with that email, a password reset link has been sent.", "info")
        
        return redirect(url_for('auth.login'))
    
    return render_template_string(FORGOT_PASSWORD_HTML)


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
@rate_limit("5 per minute")
def reset_password(token):
    """Reset password with token."""
    user_dict = database.get_user_by_reset_token(token)
    
    if not user_dict:
        flash("Invalid or expired password reset link.", "error")
        return redirect(url_for('auth.forgot_password'))
    
    if request.method == 'POST':
        password = request.form.get('password', '')
        confirm_password = request.form.get('confirm_password', '')
        
        # Validate password
        is_valid_pw, pw_error = validate_password(password)
        if not is_valid_pw:
            flash(f"Password error: {pw_error}", "error")
            return render_template_string(RESET_PASSWORD_HTML, token=token, error=pw_error)
        
        # Check passwords match
        if password != confirm_password:
            flash("Passwords do not match.", "error")
            return render_template_string(RESET_PASSWORD_HTML, token=token, error="Passwords do not match")
        
        # Update password
        password_hash = hash_password(password)
        database.update_user_password(user_dict['user_id'], password_hash)
        
        flash("Password reset successful! Please login with your new password.", "success")
        database.create_log(user_dict['user_id'], "INFO", "Password reset completed")
        return redirect(url_for('auth.login'))
    
    return render_template_string(RESET_PASSWORD_HTML, token=token)


# HTML Templates
REGISTER_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Register - AI Storybook Creator</title>
    <style>
      :root { --bg:#0e0f12; --card:#151821; --fg:#e8ecf1; --muted:#9aa5b1; --accent:#6ee7ff; --ok:#10b981; --error:#ef4444; }
      body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; color:var(--fg); background:linear-gradient(180deg, #0e0f12, #0b1020); min-height:100vh; display:flex; align-items:center; justify-content:center; }
      .card { background: var(--card); border-radius: 16px; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,.35); max-width: 400px; width: 100%; }
      h1 { margin: 0 0 10px; font-size: 28px; }
      p { color: var(--muted); margin: 0 0 20px; }
      label { display:block; margin: 14px 0 6px; color: var(--muted); font-size: 14px; }
      input[type="text"], input[type="email"], input[type="password"] { width:100%; padding:12px 14px; border-radius:10px; border:1px solid #2a2f3c; background:#0f1320; color:var(--fg); box-sizing:border-box; }
      .btn { display:inline-block; margin-top:18px; background: var(--accent); color:#001018; padding:12px 16px; border-radius: 9999px; font-weight:600; text-decoration:none; border:none; cursor:pointer; width:100%; text-align:center; }
      .btn-secondary { background: #2a2f3c; color: var(--fg); }
      .error { color: var(--error); margin-top: 10px; padding: 10px; background: rgba(239, 68, 68, 0.1); border-radius: 8px; }
      .success { color: var(--ok); margin-top: 10px; padding: 10px; background: rgba(16, 185, 129, 0.1); border-radius: 8px; }
      .link { color: var(--accent); text-decoration: none; }
      .link:hover { text-decoration: underline; }
      .footer { margin-top: 20px; text-align: center; color: var(--muted); font-size: 12px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Create Account</h1>
      <p>Sign up to save your storybooks</p>
      
      {% if error %}
      <div class="error">{{ error }}</div>
      {% endif %}
      
      <form method="POST">
        <label for="name">Name (optional)</label>
        <input type="text" name="name" id="name" placeholder="Your name" />
        
        <label for="email">Email</label>
        <input type="email" name="email" id="email" placeholder="your@email.com" required />
        
        <label for="password">Password</label>
        <input type="password" name="password" id="password" placeholder="Min 8 chars, 1 number" required />
        <small style="color: var(--muted); font-size: 12px;">Password must be at least 8 characters and contain at least one number</small>
        
        <button type="submit" class="btn">Register</button>
      </form>
      
      <div class="footer">
        Already have an account? <a href="{{ url_for('auth.login') }}" class="link">Login</a>
      </div>
    </div>
  </body>
</html>
"""

LOGIN_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Login - AI Storybook Creator</title>
    <style>
      :root { --bg:#0e0f12; --card:#151821; --fg:#e8ecf1; --muted:#9aa5b1; --accent:#6ee7ff; --ok:#10b981; --error:#ef4444; }
      body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; color:var(--fg); background:linear-gradient(180deg, #0e0f12, #0b1020); min-height:100vh; display:flex; align-items:center; justify-content:center; }
      .card { background: var(--card); border-radius: 16px; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,.35); max-width: 400px; width: 100%; }
      h1 { margin: 0 0 10px; font-size: 28px; }
      p { color: var(--muted); margin: 0 0 20px; }
      label { display:block; margin: 14px 0 6px; color: var(--muted); font-size: 14px; }
      input[type="email"], input[type="password"], input[type="checkbox"] { width:100%; padding:12px 14px; border-radius:10px; border:1px solid #2a2f3c; background:#0f1320; color:var(--fg); box-sizing:border-box; }
      input[type="checkbox"] { width: auto; margin-right: 8px; }
      .btn { display:inline-block; margin-top:18px; background: var(--accent); color:#001018; padding:12px 16px; border-radius: 9999px; font-weight:600; text-decoration:none; border:none; cursor:pointer; width:100%; text-align:center; }
      .error { color: var(--error); margin-top: 10px; padding: 10px; background: rgba(239, 68, 68, 0.1); border-radius: 8px; }
      .link { color: var(--accent); text-decoration: none; }
      .link:hover { text-decoration: underline; }
      .footer { margin-top: 20px; text-align: center; color: var(--muted); font-size: 12px; }
      .remember { display: flex; align-items: center; margin-top: 10px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Login</h1>
      <p>Sign in to your account</p>
      
      {% if error %}
      <div class="error">{{ error }}</div>
      {% endif %}
      
      <form method="POST">
        <label for="email">Email</label>
        <input type="email" name="email" id="email" placeholder="your@email.com" required />
        
        <label for="password">Password</label>
        <input type="password" name="password" id="password" placeholder="Your password" required />
        
        <div class="remember">
          <input type="checkbox" name="remember" id="remember" />
          <label for="remember" style="margin: 0;">Remember me</label>
        </div>
        
        <button type="submit" class="btn">Login</button>
      </form>
      
      <div class="footer">
        <a href="{{ url_for('auth.forgot_password') }}" class="link">Forgot password?</a><br>
        Don't have an account? <a href="{{ url_for('auth.register') }}" class="link">Register</a>
      </div>
    </div>
  </body>
</html>
"""

FORGOT_PASSWORD_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Forgot Password - AI Storybook Creator</title>
    <style>
      :root { --bg:#0e0f12; --card:#151821; --fg:#e8ecf1; --muted:#9aa5b1; --accent:#6ee7ff; }
      body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; color:var(--fg); background:linear-gradient(180deg, #0e0f12, #0b1020); min-height:100vh; display:flex; align-items:center; justify-content:center; }
      .card { background: var(--card); border-radius: 16px; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,.35); max-width: 400px; width: 100%; }
      h1 { margin: 0 0 10px; font-size: 28px; }
      p { color: var(--muted); margin: 0 0 20px; }
      label { display:block; margin: 14px 0 6px; color: var(--muted); font-size: 14px; }
      input[type="email"] { width:100%; padding:12px 14px; border-radius:10px; border:1px solid #2a2f3c; background:#0f1320; color:var(--fg); box-sizing:border-box; }
      .btn { display:inline-block; margin-top:18px; background: var(--accent); color:#001018; padding:12px 16px; border-radius: 9999px; font-weight:600; text-decoration:none; border:none; cursor:pointer; width:100%; text-align:center; }
      .link { color: var(--accent); text-decoration: none; }
      .footer { margin-top: 20px; text-align: center; color: var(--muted); font-size: 12px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Forgot Password</h1>
      <p>Enter your email and we'll send you a password reset link</p>
      
      <form method="POST">
        <label for="email">Email</label>
        <input type="email" name="email" id="email" placeholder="your@email.com" required />
        
        <button type="submit" class="btn">Send Reset Link</button>
      </form>
      
      <div class="footer">
        <a href="{{ url_for('auth.login') }}" class="link">Back to Login</a>
      </div>
    </div>
  </body>
</html>
"""

RESET_PASSWORD_HTML = """
<!doctype html>
<html lang="en">
  <head>
    <meta charset="utf-8" />
    <meta name="viewport" content="width=device-width, initial-scale=1" />
    <title>Reset Password - AI Storybook Creator</title>
    <style>
      :root { --bg:#0e0f12; --card:#151821; --fg:#e8ecf1; --muted:#9aa5b1; --accent:#6ee7ff; --error:#ef4444; }
      body { margin:0; font-family: ui-sans-serif, system-ui, -apple-system, Segoe UI, Roboto, "Helvetica Neue", Arial; color:var(--fg); background:linear-gradient(180deg, #0e0f12, #0b1020); min-height:100vh; display:flex; align-items:center; justify-content:center; }
      .card { background: var(--card); border-radius: 16px; padding: 32px; box-shadow: 0 10px 30px rgba(0,0,0,.35); max-width: 400px; width: 100%; }
      h1 { margin: 0 0 10px; font-size: 28px; }
      p { color: var(--muted); margin: 0 0 20px; }
      label { display:block; margin: 14px 0 6px; color: var(--muted); font-size: 14px; }
      input[type="password"] { width:100%; padding:12px 14px; border-radius:10px; border:1px solid #2a2f3c; background:#0f1320; color:var(--fg); box-sizing:border-box; }
      .btn { display:inline-block; margin-top:18px; background: var(--accent); color:#001018; padding:12px 16px; border-radius: 9999px; font-weight:600; text-decoration:none; border:none; cursor:pointer; width:100%; text-align:center; }
      .error { color: var(--error); margin-top: 10px; padding: 10px; background: rgba(239, 68, 68, 0.1); border-radius: 8px; }
      small { color: var(--muted); font-size: 12px; }
    </style>
  </head>
  <body>
    <div class="card">
      <h1>Reset Password</h1>
      <p>Enter your new password</p>
      
      {% if error %}
      <div class="error">{{ error }}</div>
      {% endif %}
      
      <form method="POST">
        <label for="password">New Password</label>
        <input type="password" name="password" id="password" placeholder="Min 8 chars, 1 number" required />
        <small>Password must be at least 8 characters and contain at least one number</small>
        
        <label for="confirm_password" style="margin-top: 14px;">Confirm Password</label>
        <input type="password" name="confirm_password" id="confirm_password" placeholder="Confirm new password" required />
        
        <button type="submit" class="btn">Reset Password</button>
      </form>
    </div>
  </body>
</html>
"""

