# Render Deployment - Quick Reference

## Files Created for Render

- ✅ `render.yaml` - Render service configuration
- ✅ `Procfile` - Process file for Render (alternative to render.yaml)
- ✅ `build.sh` - Build script (optional)
- ✅ `RENDER_DEPLOYMENT.md` - Full deployment guide
- ✅ `RENDER_QUICK_START.md` - Step-by-step quick start

## Quick Deployment Steps

1. **Set up external MySQL database** (PlanetScale, Railway, or AWS RDS)
2. **Push code to GitHub**
3. **Create Web Service on Render**
4. **Add environment variables** (see below)
5. **Deploy and initialize database**

## Required Environment Variables

```
OPENAI_API_KEY=sk-your-key
SECRET_KEY=your-secret-key-here
DATABASE_URL=mysql://user:pass@host:port/database
SESSION_COOKIE_SECURE=true
APP_URL=https://your-app-name.onrender.com
```

## Start Command

```
gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
```

## Build Command

```
pip install -r requirements.txt
```

## Database Initialization

After first deployment, run in Render Shell:
```bash
python init_db.py
```

## Important Notes

- **MySQL Required**: Render offers PostgreSQL, but this app uses MySQL. Use external MySQL service.
- **Free Tier**: Spins down after 15 min inactivity, ephemeral storage
- **OAuth**: Update redirect URIs after deployment
- **Storage**: Use cloud storage (S3/Cloudinary) for production

## Full Guide

See `RENDER_QUICK_START.md` for detailed step-by-step instructions.

