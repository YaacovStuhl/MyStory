# Complete Guide: Setting Up Google OAuth

This guide will walk you through setting up Google OAuth login for your MyStory application.

## Prerequisites

- A Google account
- Your Flask app running locally (or production URL)
- Access to your `.env` file

---

## Step-by-Step Setup

### Step 1: Go to Google Cloud Console

1. Visit: **https://console.cloud.google.com/**
2. Sign in with your Google account

### Step 2: Create or Select a Project

1. Click the **project dropdown** at the top of the page
2. Click **"New Project"**
3. Enter a project name (e.g., "My Story App")
4. Click **"Create"**
5. Wait a few seconds, then **select your new project** from the dropdown

### Step 3: Configure OAuth Consent Screen

**This is required before creating OAuth credentials.**

1. In the left sidebar, go to **"APIs & Services"** → **"OAuth consent screen"**
2. Choose **"External"** (unless you have a Google Workspace account)
3. Click **"Create"**
4. Fill in the required information:
   - **App name**: "My Story App" (or your preferred name)
   - **User support email**: Your email address
   - **Developer contact information**: Your email address
5. Click **"Save and Continue"**
6. On the **"Scopes"** page: Click **"Save and Continue"** (no need to add scopes)
7. On the **"Test users"** page: 
   - Click **"Add Users"** if you want to add test users
   - Click **"Save and Continue"**
8. Review and click **"Back to Dashboard"**

**Note**: For local development, you'll see a warning that the app is unverified. This is normal. Click "Advanced" → "Go to [your app name] (unsafe)" when testing.

### Step 4: Enable Required APIs

1. Go to **"APIs & Services"** → **"Library"**
2. Search for **"Google Identity"** or **"Google+ API"**
3. Click on it and click **"Enable"**

### Step 5: Create OAuth 2.0 Client ID

1. Go to **"APIs & Services"** → **"Credentials"**
2. Click **"+ CREATE CREDENTIALS"** at the top
3. Select **"OAuth client ID"**
4. If prompted, select **"Web application"** as the application type
5. Fill in the form:
   - **Name**: "My Story App Web Client" (or any name)
   - **Authorized JavaScript origins**: 
     - For local: `http://localhost:5000`
     - For production: `https://your-domain.com` (add this later)
   - **Authorized redirect URIs**: 
     - For local: `http://localhost:5000/auth/google/callback`
     - For production: `https://your-domain.com/auth/google/callback` (add this later)
6. Click **"Create"**

### Step 6: Copy Your Credentials

After creating the OAuth client, you'll see a popup with:

- **Client ID**: Looks like `123456789-abc123def456.apps.googleusercontent.com`
- **Client secret**: Looks like `GOCSPX-abc123xyz789`

**⚠️ IMPORTANT**: Copy both values immediately! The client secret will only be shown once.

### Step 7: Configure Your .env File

1. Open your `.env` file in the `MyStory` directory
2. **IMPORTANT**: Generate a SECRET_KEY first:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Copy the output - you'll need it in the next step.

3. Add the following to your `.env` file (or update if they already exist):

```env
# REQUIRED for OAuth sessions - MUST be a fixed value!
# If this changes, OAuth will fail with "CSRF state mismatch" error
SECRET_KEY=your-generated-secret-key-here-paste-from-step-2

# Google OAuth Credentials
GOOGLE_CLIENT_ID=your-client-id-here.apps.googleusercontent.com
GOOGLE_CLIENT_SECRET=GOCSPX-your-client-secret-here

# Optional: Override redirect URI if needed
# GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback

# Optional: Override base URL for OAuth (default: http://localhost:5000)
# OAUTH_BASE_URL=http://localhost:5000
```

4. Replace the placeholder values:
   - Paste your generated `SECRET_KEY` from step 2
   - Paste your `GOOGLE_CLIENT_ID` from Step 6
   - Paste your `GOOGLE_CLIENT_SECRET` from Step 6

**⚠️ CRITICAL**: The `SECRET_KEY` must be a **fixed value** in your `.env` file. If it changes (or is randomly generated), OAuth will fail with a "CSRF state mismatch" error.

### Step 8: Verify Database Schema

Make sure your database has the OAuth fields.

**For MySQL/XAMPP:**
1. Navigate to your MyStory directory:
   ```bash
   cd C:\xampp\htdocs\MyStory\MyStory
   ```
2. Run the MySQL migration script:
   ```bash
   python migrate_oauth_schema_mysql.py
   ```

**Note**: If you recently ran `init_db.py`, the OAuth columns may already exist. The migration script will check and skip if they're already there.

**Or manually verify** that your `users` table has:
- `oauth_provider` column
- `oauth_id` column  
- `name` column

You can check in phpMyAdmin or MySQL:
```sql
DESCRIBE users;
```

### Step 9: Restart Your Flask App

1. Stop your Flask app (Ctrl+C)
2. Restart it:
   ```bash
   python app.py
   # or
   flask run
   ```

### Step 10: Test Google OAuth

1. Visit `http://localhost:5000`
2. Look for the **"Login with Google"** button
3. Click it
4. You should be redirected to Google's login page
5. Sign in with your Google account
6. You may see a warning about the app being unverified (normal for development)
   - Click **"Advanced"**
   - Click **"Go to [your app name] (unsafe)"**
7. After authorizing, you should be redirected back to your app
8. You should now be logged in!

---

## Troubleshooting

### Error: "CSRF state mismatch" or "mismatching_state"

**Cause**: The SECRET_KEY changed between when you started OAuth and when Google redirected back, or session cookies aren't working.

**Solution**:
1. **Check your `.env` file** - Make sure `SECRET_KEY` is set and is a fixed value (not randomly generated)
2. **Generate a new SECRET_KEY** if needed:
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
3. **Add it to `.env`**:
   ```env
   SECRET_KEY=your-generated-key-here
   ```
4. **Clear browser cookies** for localhost:5000
5. **Restart your Flask app**
6. **Try OAuth login again**

**Common causes**:
- SECRET_KEY not set in `.env` (app generates random one each restart)
- Browser cookies blocked or cleared
- Using incognito/private browsing mode
- Different browser between OAuth start and callback

### Error: "Redirect URI mismatch"

**Cause**: The redirect URI in Google Console doesn't match what your app is sending.

**Solution**:
1. Check the app logs - it will show the redirect URI being used
2. Go to Google Cloud Console → Credentials → Your OAuth Client
3. Make sure **Authorized redirect URIs** includes exactly:
   - `http://localhost:5000/auth/google/callback` (for local)
   - No trailing slashes
   - Exact match (http vs https matters)
4. If you're using `127.0.0.1` instead of `localhost`, add that too:
   - `http://127.0.0.1:5000/auth/google/callback`

**Quick Fix**: You can also set a custom redirect URI in your `.env`:
```env
GOOGLE_REDIRECT_URI=http://localhost:5000/auth/google/callback
```

### Error: "OAuth not configured"

**Cause**: Missing credentials or authlib not installed.

**Solution**:
1. Check that `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` are in your `.env`
2. Verify `authlib` is installed: `pip install authlib`
3. Restart your Flask app after adding credentials

### Error: "App not verified" warning

**Cause**: This is normal for development apps.

**Solution**:
- Click **"Advanced"** → **"Go to [your app name] (unsafe)"**
- For production, you'll need to verify your app with Google (requires domain verification)

### Error: "Invalid client" or "Invalid credentials"

**Cause**: Wrong Client ID or Secret.

**Solution**:
1. Double-check your `.env` file
2. Make sure there are no extra spaces or quotes
3. Copy the credentials again from Google Console
4. Restart your Flask app

### Can't find "Credentials" page

**Solution**:
1. Make sure you've selected your project (check the project dropdown)
2. Go to: **APIs & Services** → **Credentials**
3. If you don't see it, make sure you've completed the OAuth consent screen setup first

---

## Production Setup

When deploying to production:

1. **Update Redirect URIs in Google Console**:
   - Add your production domain: `https://your-domain.com/auth/google/callback`
   - Add your production origin: `https://your-domain.com`

2. **Update .env** (or use environment variables):
   ```env
   OAUTH_BASE_URL=https://your-domain.com
   # or
   GOOGLE_REDIRECT_URI=https://your-domain.com/auth/google/callback
   ```

3. **Verify Your App**:
   - Go to OAuth consent screen
   - Submit for verification (required for public use)
   - This process can take several days

4. **Add Production Domain**:
   - In OAuth consent screen → Authorized domains
   - Add your production domain

---

## How It Works

1. User clicks "Login with Google"
2. App redirects to Google's authorization page
3. User signs in and authorizes your app
4. Google redirects back to `/auth/google/callback` with an authorization code
5. App exchanges the code for user information (email, name, etc.)
6. App creates or finds the user account
7. User is logged in via session

---

## Security Notes

- **Never commit your `.env` file** to version control
- Keep your **Client Secret** secure
- Use **HTTPS in production**
- Set a strong **SECRET_KEY** for session encryption
- Regularly rotate your OAuth credentials

---

## Quick Reference

**Google Cloud Console**: https://console.cloud.google.com/

**Required Redirect URI** (local): `http://localhost:5000/auth/google/callback`

**Required Redirect URI** (production): `https://your-domain.com/auth/google/callback`

**Environment Variables Needed**:
- `GOOGLE_CLIENT_ID`
- `GOOGLE_CLIENT_SECRET`
- `SECRET_KEY` (for sessions)

---

## Still Having Issues?

1. Check the Flask app logs for error messages
2. Verify all environment variables are set correctly
3. Make sure the redirect URI in Google Console matches exactly
4. Try clearing your browser cookies and cache
5. Check that `authlib` is installed: `pip list | grep authlib`
