# Quick Guide: Setting Up Google OAuth

## Step-by-Step Instructions

### 1. Go to Google Cloud Console
Visit: https://console.cloud.google.com/

### 2. Create or Select a Project
- Click the project dropdown at the top
- Click "New Project"
- Name it something like "My Story App"
- Click "Create"
- Wait a few seconds, then select your new project

### 3. Enable Google+ API (or Google Identity API)
- In the left sidebar, click "APIs & Services" → "Library"
- Search for "Google+ API" or "Google Identity"
- Click on it and click "Enable"

### 4. Create OAuth Credentials
- Go to "APIs & Services" → "Credentials"
- Click "+ CREATE CREDENTIALS" at the top
- Select "OAuth client ID"

### 5. Configure OAuth Consent Screen (First Time Only)
If this is your first time, you'll need to set up the consent screen:
- Choose "External" (unless you have a Google Workspace)
- Click "Create"
- Fill in:
  - App name: "My Story App" (or any name)
  - User support email: Your email
  - Developer contact: Your email
- Click "Save and Continue"
- On "Scopes" page, click "Save and Continue"
- On "Test users" page, click "Save and Continue"
- Review and click "Back to Dashboard"

### 6. Create OAuth Client ID
- Application type: Select "Web application"
- Name: "My Story App Web Client" (or any name)
- Authorized JavaScript origins: 
  - For local testing: `http://localhost:5000`
  - For production: `https://your-domain.com` (add later)
- Authorized redirect URIs:
  - For local testing: `http://localhost:5000/auth/google/callback`
  - For production: `https://your-domain.com/auth/google/callback` (add later)
- Click "Create"

### 7. Copy Your Credentials
- You'll see a popup with:
  - **Client ID** (looks like: `123456789-abc123.apps.googleusercontent.com`)
  - **Client secret** (looks like: `GOCSPX-abc123xyz`)
- Copy both of these!

### 8. Add to Your .env File
Open your `.env` file and add:

```env
GOOGLE_CLIENT_ID=your-client-id-here
GOOGLE_CLIENT_SECRET=your-client-secret-here
```

Replace `your-client-id-here` and `your-client-secret-here` with the actual values you copied.

### 9. Restart Your Flask App
```bash
flask run
```

### 10. Test It!
- Visit `http://localhost:5000`
- Click "Login with Google"
- You should see Google's login page
- After logging in, you'll be redirected back to your app

## Important Notes

⚠️ **For Local Testing:**
- Google may show a warning about the app not being verified (this is normal for development)
- Click "Advanced" → "Go to My Story App (unsafe)" to proceed
- You can add test users in the OAuth consent screen settings

⚠️ **For Production:**
- You'll need to verify your app with Google (requires domain verification)
- Update the redirect URIs to your production domain
- The app must be published in the consent screen

## Troubleshooting

**"Redirect URI mismatch" error:**
- Make sure the redirect URI in Google Console exactly matches: `http://localhost:5000/auth/google/callback`
- Check for typos, http vs https, trailing slashes

**"App not verified" warning:**
- This is normal for development
- Click "Advanced" → "Go to [your app name] (unsafe)"

**Can't find Credentials page:**
- Make sure you've selected your project
- Go to: APIs & Services → Credentials

