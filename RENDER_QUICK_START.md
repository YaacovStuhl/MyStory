# Render Deployment - Quick Start Guide

## Prerequisites Checklist

- [ ] GitHub repository with your code
- [ ] Render account (free tier works)
- [ ] OpenAI API key
- [ ] MySQL database (external service - see options below)
- [ ] SECRET_KEY (generate one)

## Step 1: Prepare Your Code

1. **Commit all files to Git:**
   ```bash
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

2. **Generate a SECRET_KEY:**
   ```bash
   python -c "import secrets; print(secrets.token_urlsafe(32))"
   ```
   Copy this value - you'll need it in Step 3.

## Step 2: Create PostgreSQL Database on Render

**The app now supports PostgreSQL!** Render offers PostgreSQL by default, so you can use it directly:

1. In Render dashboard, go to **"New +"** → **"PostgreSQL"**
2. Configure:
   - **Name**: `mystory-db` (or any name)
   - **Database**: `mystory`
   - **User**: `mystory_user` (or any name)
   - **Region**: Same as your web service
   - **Plan**: Free (for testing) or Starter (for production)
3. Click **"Create Database"**
4. The `DATABASE_URL` will be automatically set in your web service environment variables

**Note**: The app automatically detects PostgreSQL vs MySQL from the connection string, so no code changes needed!

## Step 3: Deploy to Render

### 3.1 Create Web Service

1. Go to https://dashboard.render.com
2. Click **"New +"** → **"Web Service"**
3. Connect your GitHub repository
4. Select your repository and branch

### 3.2 Configure Service

**Basic Settings:**
- **Name**: `mystory-app` (or any name)
- **Environment**: `Python 3`
- **Region**: Choose closest to you
- **Branch**: `main` (or your default branch)

**Build & Deploy:**
- **Build Command**: `pip install -r requirements.txt`
- **Start Command**: `gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app`

### 3.3 Add Environment Variables

Click **"Environment"** tab and add:

**Required:**
```
OPENAI_API_KEY=sk-your-key-here
SECRET_KEY=your-generated-secret-key-from-step-1
DATABASE_URL=postgresql://user:pass@host:port/database
# Note: DATABASE_URL is automatically set if you use Render PostgreSQL database
SESSION_COOKIE_SECURE=true
APP_URL=https://your-app-name.onrender.com
```

**Optional (for OAuth):**
```
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
FACEBOOK_CLIENT_ID=your-facebook-app-id
FACEBOOK_CLIENT_SECRET=your-facebook-app-secret
APPLE_CLIENT_ID=your-apple-service-id
APPLE_CLIENT_SECRET=your-apple-client-secret
```

**Optional (for email):**
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
```

### 3.4 Deploy

1. Click **"Create Web Service"**
2. Wait for first deployment (5-10 minutes)
3. Watch the logs for any errors

### 3.5 Initialize Database

After first successful deployment:

1. Go to **"Shell"** tab in Render dashboard
2. Run:
   ```bash
   python init_db.py
   ```
3. This creates tables and loads storylines

## Step 4: Update OAuth Redirect URIs

After deployment, update OAuth providers:

1. **Google**: https://console.cloud.google.com/apis/credentials
   - Add: `https://your-app-name.onrender.com/auth/google/callback`

2. **Facebook**: https://developers.facebook.com/apps/
   - Add: `https://your-app-name.onrender.com/auth/facebook/callback`

3. **Apple**: https://developer.apple.com/account/resources/identifiers/list
   - Add: `https://your-app-name.onrender.com/auth/apple/callback`

## Step 5: Test Your App

1. Visit: `https://your-app-name.onrender.com`
2. Test storybook generation
3. Test OAuth login (if configured)
4. Check dashboard

## Troubleshooting

### Build Fails

- Check `requirements.txt` has all dependencies
- Check Python version (app uses 3.11)
- Check build logs for specific errors

### Database Connection Fails

- Verify `DATABASE_URL` format is correct (should start with `postgresql://`)
- If using Render PostgreSQL, the connection string is set automatically
- Check database is accessible from Render's IPs (should work automatically on Render)
- Test connection string locally first if using external database

### App Crashes on Start

- Check start command is correct
- Check logs for Python errors
- Verify all environment variables are set

### OAuth Not Working

- Verify redirect URIs are updated
- Check `SESSION_COOKIE_SECURE=true`
- Check `APP_URL` matches your Render URL
- Verify `SECRET_KEY` is set

### Timeout Errors

- Increase timeout in start command if needed
- Check OpenAI API is responding
- Consider reducing `MAX_IMAGE_WORKERS`

## Important Notes

### Free Tier Limitations

- **Spins down** after 15 minutes of inactivity
- **First request** after spin-down takes 30-60 seconds
- **Ephemeral storage** - files deleted on restart
- **Limited resources** - may be slow

### Production Recommendations

1. **Upgrade to paid plan** for better performance
2. **Use cloud storage** (S3, Cloudinary) for uploads/PDFs
3. **Set up monitoring** and alerts
4. **Configure custom domain** with SSL

## Next Steps

- Set up cloud storage for user uploads
- Configure custom domain
- Set up monitoring
- Enable backups

