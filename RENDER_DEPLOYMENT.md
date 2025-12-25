# Render Deployment Guide

This guide will help you deploy the MyStory application to Render.

## Prerequisites

1. A Render account (sign up at https://render.com)
2. A GitHub repository with your code (or GitLab/Bitbucket)
3. OpenAI API key
4. OAuth credentials (optional, for Google/Facebook/Apple login)

## Step 1: Prepare Your Repository

1. **Make sure all files are committed to Git:**
   ```bash
   git add .
   git commit -m "Prepare for Render deployment"
   git push origin main
   ```

2. **Verify these files exist in your repository:**
   - `requirements.txt` ✅
   - `render.yaml` ✅
   - `app.py` ✅
   - `init_db.py` ✅
   - `schema.sql` ✅
   - `database.py` ✅

## Step 2: Create Database on Render

**IMPORTANT**: This app uses **MySQL**, but Render offers **PostgreSQL** by default. You have two options:

### Option A: Use External MySQL Service (Recommended)

Use an external MySQL service that works with Render:
- **PlanetScale** (free tier available) - https://planetscale.com
- **AWS RDS MySQL** (pay-as-you-go)
- **Railway MySQL** (free tier available)
- **Aiven MySQL** (free tier available)

1. Create a MySQL database on your chosen service
2. Get the connection string (format: `mysql://user:password@host:port/database`)
3. Use this connection string in Step 3 as `DATABASE_URL`

### Option B: Use Render PostgreSQL (Requires Code Changes)

If you want to use Render's PostgreSQL, you'll need to:
1. Install PostgreSQL adapter: `pip install psycopg2-binary`
2. Update `database.py` to support PostgreSQL
3. Update `schema.sql` to use PostgreSQL syntax

**For now, we'll proceed with Option A (External MySQL).**

2. **Database Settings:**
   - **Name**: `mystory-db`
   - **Database**: `mystory`
   - **User**: `mystory_user`
   - **Plan**: Free (or paid for production)

3. **Copy the Internal Database URL** (you'll need this later)

## Step 3: Create Web Service on Render

1. **Go to Render Dashboard** → **New** → **Web Service**

2. **Connect your repository:**
   - Connect GitHub/GitLab/Bitbucket
   - Select your repository
   - Select the branch (usually `main` or `master`)

3. **Configure the service:**
   - **Name**: `mystory-app`
   - **Environment**: `Python 3`
   - **Build Command**: `pip install -r requirements.txt && python init_db.py`
   - **Start Command**: `gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app`
   - **Plan**: Free (or paid for production)

4. **Add Environment Variables:**
   
   **Required:**
   - `OPENAI_API_KEY` = `sk-your-key-here`
   - `SECRET_KEY` = Generate with: `python -c "import secrets; print(secrets.token_urlsafe(32))"`
   - `DATABASE_URL` = Your database connection string from Step 2
   - `SESSION_COOKIE_SECURE` = `true` (for HTTPS)
   - `APP_URL` = `https://your-app-name.onrender.com` (your Render app URL)

   **Optional (for OAuth):**
   - `GOOGLE_CLIENT_ID` = Your Google OAuth client ID
   - `GOOGLE_CLIENT_SECRET` = Your Google OAuth client secret
   - `FACEBOOK_CLIENT_ID` = Your Facebook app ID
   - `FACEBOOK_CLIENT_SECRET` = Your Facebook app secret
   - `APPLE_CLIENT_ID` = Your Apple service ID
   - `APPLE_CLIENT_SECRET` = Your Apple client secret

   **Optional (for email):**
   - `SMTP_HOST` = `smtp.gmail.com`
   - `SMTP_PORT` = `587`
   - `SMTP_USER` = Your email
   - `SMTP_PASSWORD` = Your app password
   - `SMTP_FROM` = Your email

   **Optional (tuning):**
   - `MODEL_VISION` = `gpt-4o-mini` (default)
   - `MAX_IMAGE_WORKERS` = `6` (default)

## Step 4: Update OAuth Redirect URIs

After your app is deployed, update the OAuth redirect URIs in each provider:

1. **Google OAuth Console:**
   - Add: `https://your-app-name.onrender.com/auth/google/callback`

2. **Facebook Developer Console:**
   - Add: `https://your-app-name.onrender.com/auth/facebook/callback`

3. **Apple Developer Console:**
   - Add: `https://your-app-name.onrender.com/auth/apple/callback`

## Step 5: Deploy

1. **Click "Create Web Service"** in Render
2. Render will:
   - Clone your repository
   - Install dependencies
   - Run `init_db.py` to set up the database
   - Start the app with Gunicorn

3. **Wait for deployment** (first deploy takes 5-10 minutes)

4. **Check logs** if there are any errors

## Step 6: Verify Deployment

1. **Visit your app URL**: `https://your-app-name.onrender.com`
2. **Test the application:**
   - Upload a child photo
   - Generate a storybook
   - Test OAuth login (if configured)
   - Check dashboard

## Troubleshooting

### Database Connection Issues

If you see database connection errors:

1. **Check DATABASE_URL format:**
   - For PostgreSQL: `postgresql://user:pass@host:port/dbname`
   - For MySQL: `mysql://user:pass@host:port/dbname`

2. **Verify database is running** in Render dashboard

3. **Check database credentials** match your environment variables

### App Won't Start

1. **Check build logs** in Render dashboard
2. **Verify requirements.txt** has all dependencies
3. **Check start command** is correct
4. **Look for Python version issues** (app uses Python 3.11)

### OAuth Not Working

1. **Verify redirect URIs** are updated in OAuth provider consoles
2. **Check SESSION_COOKIE_SECURE** is set to `true` (for HTTPS)
3. **Verify SECRET_KEY** is set and not changing
4. **Check APP_URL** matches your Render app URL

### Timeout Issues

1. **Increase timeout** in start command if needed
2. **Check image generation** isn't taking too long
3. **Verify OpenAI API** is responding

### Static Files Not Loading

1. **Check static folder** is in repository
2. **Verify file paths** are correct
3. **Check Render file system** (free tier has ephemeral storage)

## Important Notes

### Free Tier Limitations

- **Spins down after 15 minutes** of inactivity
- **First request** after spin-down takes 30-60 seconds
- **Ephemeral storage** - files are deleted on restart
- **Limited resources** - may be slow for image generation

### Production Recommendations

1. **Use paid plan** for better performance
2. **Set up persistent storage** (S3, Cloudinary) for user uploads
3. **Use external MySQL** (PlanetScale, AWS RDS) for better reliability
4. **Set up monitoring** and alerts
5. **Configure custom domain** with SSL

### File Storage

The free tier has **ephemeral storage**, meaning:
- Uploaded images are deleted when the app restarts
- Generated PDFs are deleted when the app restarts
- **Solution**: Use cloud storage (S3, Cloudinary) for production

## Environment Variables Reference

See `env.sample` for all available environment variables.

## Support

If you encounter issues:
1. Check Render logs
2. Check application logs at `/admin/logs` (if logged in)
3. Review error messages in Render dashboard

