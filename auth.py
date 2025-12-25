"""
Authentication utilities for email/password login.
Handles password hashing, validation, email verification, and password reset.
"""

import os
import re
import secrets
import logging
from datetime import datetime, timedelta
from typing import Optional, Tuple
from werkzeug.security import generate_password_hash, check_password_hash
from email_validator import validate_email, EmailNotValidError

# Email configuration
SMTP_HOST = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT = int(os.getenv("SMTP_PORT", "587"))
SMTP_USER = os.getenv("SMTP_USER", "")
SMTP_PASSWORD = os.getenv("SMTP_PASSWORD", "")
SMTP_FROM = os.getenv("SMTP_FROM", SMTP_USER)
APP_URL = os.getenv("APP_URL", "http://localhost:5000")


def validate_password(password: str) -> Tuple[bool, Optional[str]]:
    """
    Validate password meets requirements.
    
    Requirements:
    - Minimum 8 characters
    - At least 1 number
    
    Returns:
        (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r'\d', password):
        return False, "Password must contain at least one number"
    
    return True, None


def hash_password(password: str) -> str:
    """Hash a password using Werkzeug's password hashing."""
    return generate_password_hash(password)


def verify_password(password_hash: str, password: str) -> bool:
    """Verify a password against its hash."""
    return check_password_hash(password_hash, password)


def validate_email_address(email: str) -> Tuple[bool, Optional[str]]:
    """
    Validate email address format.
    
    Returns:
        (is_valid, error_message)
    """
    try:
        validate_email(email)
        return True, None
    except EmailNotValidError as e:
        return False, str(e)


def generate_token(length: int = 32) -> str:
    """Generate a secure random token."""
    return secrets.token_urlsafe(length)


def send_verification_email(email: str, name: str, token: str) -> bool:
    """
    Send email verification link.
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logging.warning("[auth] SMTP not configured - email verification disabled")
        logging.warning("[auth] Set SMTP_USER and SMTP_PASSWORD in .env to enable email verification")
        return False
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        verification_url = f"{APP_URL}/verify-email/{token}"
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Verify Your Email - AI Storybook Creator"
        msg['From'] = SMTP_FROM
        msg['To'] = email
        
        # Plain text version
        text = f"""Hello {name},

Please verify your email address by clicking the link below:

{verification_url}

This link will expire in 24 hours.

If you didn't create an account, please ignore this email.

Best regards,
AI Storybook Creator Team
"""
        
        # HTML version
        html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #6ee7ff; color: #001018; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 20px 0; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Hello {name}!</h2>
        <p>Please verify your email address by clicking the button below:</p>
        <a href="{verification_url}" class="button">Verify Email</a>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #666;">{verification_url}</p>
        <p>This link will expire in 24 hours.</p>
        <p>If you didn't create an account, please ignore this email.</p>
        <div class="footer">
            <p>Best regards,<br>AI Storybook Creator Team</p>
        </div>
    </div>
</body>
</html>
"""
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        logging.info(f"[auth] Verification email sent to {email}")
        return True
        
    except Exception as e:
        logging.error(f"[auth] Failed to send verification email: {e}")
        return False


def send_password_reset_email(email: str, name: str, token: str) -> bool:
    """
    Send password reset link.
    
    Returns:
        True if email sent successfully, False otherwise
    """
    if not SMTP_USER or not SMTP_PASSWORD:
        logging.warning("[auth] SMTP not configured - password reset disabled")
        return False
    
    try:
        import smtplib
        from email.mime.text import MIMEText
        from email.mime.multipart import MIMEMultipart
        
        reset_url = f"{APP_URL}/reset-password/{token}"
        
        msg = MIMEMultipart('alternative')
        msg['Subject'] = "Reset Your Password - AI Storybook Creator"
        msg['From'] = SMTP_FROM
        msg['To'] = email
        
        # Plain text version
        text = f"""Hello {name},

You requested to reset your password. Click the link below to reset it:

{reset_url}

This link will expire in 1 hour.

If you didn't request a password reset, please ignore this email.

Best regards,
AI Storybook Creator Team
"""
        
        # HTML version
        html = f"""<!DOCTYPE html>
<html>
<head>
    <style>
        body {{ font-family: Arial, sans-serif; line-height: 1.6; color: #333; }}
        .container {{ max-width: 600px; margin: 0 auto; padding: 20px; }}
        .button {{ display: inline-block; padding: 12px 24px; background-color: #6ee7ff; color: #001018; text-decoration: none; border-radius: 5px; font-weight: bold; margin: 20px 0; }}
        .footer {{ margin-top: 30px; font-size: 12px; color: #666; }}
        .warning {{ color: #d32f2f; font-weight: bold; }}
    </style>
</head>
<body>
    <div class="container">
        <h2>Hello {name}!</h2>
        <p>You requested to reset your password. Click the button below to reset it:</p>
        <a href="{reset_url}" class="button">Reset Password</a>
        <p>Or copy and paste this link into your browser:</p>
        <p style="word-break: break-all; color: #666;">{reset_url}</p>
        <p class="warning">This link will expire in 1 hour.</p>
        <p>If you didn't request a password reset, please ignore this email.</p>
        <div class="footer">
            <p>Best regards,<br>AI Storybook Creator Team</p>
        </div>
    </div>
</body>
</html>
"""
        
        part1 = MIMEText(text, 'plain')
        part2 = MIMEText(html, 'html')
        
        msg.attach(part1)
        msg.attach(part2)
        
        with smtplib.SMTP(SMTP_HOST, SMTP_PORT) as server:
            server.starttls()
            server.login(SMTP_USER, SMTP_PASSWORD)
            server.send_message(msg)
        
        logging.info(f"[auth] Password reset email sent to {email}")
        return True
        
    except Exception as e:
        logging.error(f"[auth] Failed to send password reset email: {e}")
        return False

