# OAuth Login Setup Guide

This application supports OAuth login with Google, Facebook, and Apple Sign In.

## Features

- ✅ Google (Gmail) OAuth login
- ✅ Facebook OAuth login  
- ✅ Apple Sign In
- ✅ Account linking (if email already exists)
- ✅ User dashboard to view saved storybooks
- ✅ Session management

## Setup Instructions

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

This will install `authlib` which handles OAuth.

### 2. Update Database Schema

Run the migration script to add OAuth fields to the users table:

```bash
python migrate_oauth_schema.py
```

Or manually run:
```sql
ALTER TABLE users ADD COLUMN oauth_id VARCHAR(255) AFTER oauth_provider;
ALTER TABLE users ADD COLUMN name VARCHAR(255) AFTER oauth_id;
ALTER TABLE users ADD UNIQUE KEY unique_oauth (oauth_provider, oauth_id);
```

### 3. Configure OAuth Providers

Add OAuth credentials to your `.env` file:

```env
# Required for sessions
SECRET_KEY=your-random-secret-key-here

# Google OAuth
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret

# Facebook OAuth
FACEBOOK_CLIENT_ID=your-facebook-app-id
FACEBOOK_CLIENT_SECRET=your-facebook-app-secret

# Apple Sign In
APPLE_CLIENT_ID=your-apple-service-id
APPLE_CLIENT_SECRET=your-apple-client-secret
```

### 4. Get OAuth Credentials

#### Google OAuth

1. Go to [Google Cloud Console](https://console.cloud.google.com/)
2. Create a new project or select existing
3. Enable Google+ API
4. Go to "Credentials" → "Create Credentials" → "OAuth client ID"
5. Application type: Web application
6. Authorized redirect URIs: `http://localhost:5000/auth/google/callback` (for local)
7. Copy Client ID and Client Secret

#### Facebook OAuth

1. Go to [Facebook Developers](https://developers.facebook.com/apps/)
2. Create a new app
3. Add "Facebook Login" product
4. Settings → Basic: Add your domain and redirect URI
5. Settings → Facebook Login → Settings:
   - Valid OAuth Redirect URIs: `http://localhost:5000/auth/facebook/callback`
6. Copy App ID and App Secret

#### Apple Sign In

1. Go to [Apple Developer](https://developer.apple.com/account/)
2. Create a Services ID
3. Enable "Sign in with Apple"
4. Configure domains and redirect URLs
5. Create a Key for Sign in with Apple
6. Use Service ID as Client ID
7. Generate client secret using the key

### 5. Update Redirect URIs for Production

When deploying to Render or another host, update the redirect URIs in each provider's console:

- Google: `https://your-domain.com/auth/google/callback`
- Facebook: `https://your-domain.com/auth/facebook/callback`
- Apple: `https://your-domain.com/auth/apple/callback`

## How It Works

### Login Flow

1. User clicks "Login with [Provider]" button
2. Redirected to provider's login page
3. User authorizes the application
4. Provider redirects back with authorization code
5. Application exchanges code for user info
6. User account is created or linked
7. User is logged in and redirected to dashboard

### Account Linking

If a user tries to login with a different OAuth provider but the email already exists:
- The OAuth account is automatically linked to the existing user account
- User can login with any linked provider
- All storybooks are associated with the same user account

### User Dashboard

After login, users can:
- View all their generated storybooks
- Download PDFs
- See creation dates
- Access from `/dashboard` route

## Routes

- `/login/google` - Initiate Google login
- `/login/facebook` - Initiate Facebook login
- `/login/apple` - Initiate Apple login
- `/auth/google/callback` - Google callback handler
- `/auth/facebook/callback` - Facebook callback handler
- `/auth/apple/callback` - Apple callback handler
- `/dashboard` - User dashboard (requires login)
- `/logout` - Logout and clear session

## Testing

1. Start the Flask app: `flask run`
2. Visit `http://localhost:5000`
3. Click a login button (e.g., "Login with Google")
4. Complete OAuth flow
5. Should redirect to dashboard
6. Create a storybook - it will be saved to your account
7. View it in the dashboard

## Troubleshooting

### "OAuth not configured" error
- Check that OAuth credentials are set in `.env`
- Verify `authlib` is installed: `pip install authlib`
- Check that provider is registered in app initialization

### Redirect URI mismatch
- Ensure redirect URI in provider console matches exactly
- Include protocol (http/https) and port
- Check for trailing slashes

### Account linking not working
- Verify database has `oauth_id` and `name` columns
- Run migration script: `python migrate_oauth_schema.py`
- Check database logs for errors

### Session not persisting
- Ensure `SECRET_KEY` is set in `.env`
- Check browser allows cookies
- Verify Flask session configuration

