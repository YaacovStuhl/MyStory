# Google OAuth Setup - Quick Checklist

Use this checklist to quickly set up Google OAuth for your app.

## ✅ Pre-Setup Checklist

- [ ] Have a Google account
- [ ] Flask app is installed and working
- [ ] Have access to your `.env` file
- [ ] `authlib` is installed (`pip install authlib`)

## ✅ Step-by-Step Checklist

### 1. Google Cloud Console Setup
- [ ] Go to https://console.cloud.google.com/
- [ ] Create a new project (or select existing)
- [ ] Note your project name: ________________

### 2. OAuth Consent Screen
- [ ] Go to: APIs & Services → OAuth consent screen
- [ ] Choose "External"
- [ ] Fill in:
  - [ ] App name: ________________
  - [ ] User support email: ________________
  - [ ] Developer contact: ________________
- [ ] Click through all pages (Save and Continue)
- [ ] Return to dashboard

### 3. Enable APIs
- [ ] Go to: APIs & Services → Library
- [ ] Search "Google Identity" or "Google+ API"
- [ ] Click "Enable"

### 4. Create OAuth Credentials
- [ ] Go to: APIs & Services → Credentials
- [ ] Click "+ CREATE CREDENTIALS" → "OAuth client ID"
- [ ] Application type: **Web application**
- [ ] Name: ________________
- [ ] Authorized JavaScript origins: `http://localhost:5000`
- [ ] Authorized redirect URIs: `http://localhost:5000/auth/google/callback`
- [ ] Click "Create"
- [ ] **COPY BOTH VALUES NOW** (secret won't show again!)

### 5. Get Your Credentials
- [ ] Client ID: `________________________________________________`
- [ ] Client Secret: `________________________________________________`

### 6. Configure .env File
- [ ] Generate SECRET_KEY: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Copy the generated SECRET_KEY: `________________________________________________`
- [ ] Open `.env` file
- [ ] Add/update:
  ```env
  SECRET_KEY=your-generated-secret-key-here
  GOOGLE_CLIENT_ID=your-client-id-here
  GOOGLE_CLIENT_SECRET=your-client-secret-here
  ```
- [ ] **IMPORTANT**: SECRET_KEY must be fixed - don't let it change!

### 7. Database Setup
- [ ] Navigate to MyStory directory: `cd C:\xampp\htdocs\MyStory\MyStory`
- [ ] Run: `python migrate_oauth_schema_mysql.py` (for MySQL/XAMPP)
- [ ] Or verify database has `oauth_provider`, `oauth_id`, `name` columns
- [ ] Note: If you ran `init_db.py` recently, columns may already exist

### 8. Restart App
- [ ] Stop Flask app (Ctrl+C)
- [ ] Restart: `python app.py` or `flask run`

### 9. Test
- [ ] Visit: http://localhost:5000
- [ ] Click "Login with Google"
- [ ] Sign in with Google account
- [ ] If warning appears: Click "Advanced" → "Go to [app name] (unsafe)"
- [ ] Should redirect back and be logged in!

## ❌ Common Issues & Quick Fixes

### CSRF State Mismatch
- [ ] Check `.env` has `SECRET_KEY` set (not randomly generated)
- [ ] Generate new SECRET_KEY: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
- [ ] Add to `.env`: `SECRET_KEY=your-key-here`
- [ ] Clear browser cookies for localhost:5000
- [ ] Restart Flask app
- [ ] Try OAuth login again

### Redirect URI Mismatch
- [ ] Check Google Console → Credentials → Your OAuth Client
- [ ] Verify redirect URI is exactly: `http://localhost:5000/auth/google/callback`
- [ ] No trailing slash, exact match
- [ ] Restart Flask app

### OAuth Not Configured
- [ ] Check `.env` has `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET`
- [ ] Verify `authlib` installed: `pip list | grep authlib`
- [ ] Restart Flask app

### Can't Find Credentials Page
- [ ] Make sure project is selected (top dropdown)
- [ ] Complete OAuth consent screen first
- [ ] Go to: APIs & Services → Credentials

## 📝 Notes

- Redirect URI must match **exactly** (including http/https, localhost vs 127.0.0.1)
- Client secret is only shown once - save it immediately!
- For production, add your production domain to redirect URIs
- App verification warning is normal for development

## 🔗 Quick Links

- Google Cloud Console: https://console.cloud.google.com/
- Your OAuth Client: APIs & Services → Credentials → [Your Client Name]
- OAuth Consent Screen: APIs & Services → OAuth consent screen

