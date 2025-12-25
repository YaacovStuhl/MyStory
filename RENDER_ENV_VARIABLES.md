# Render Environment Variables Guide

## ✅ **REQUIRED - Must Add to Render**

These are essential for your app to work:

```
OPENAI_API_KEY=sk-your-key-here
SECRET_KEY=your-secret-key-here
APP_URL=https://your-app-name.onrender.com
```

**Notes:**
- `OPENAI_API_KEY`: Your OpenAI API key (required for image generation)
- `SECRET_KEY`: Generate with `python -c "import secrets; print(secrets.token_urlsafe(32))"` (required for OAuth sessions)
- `APP_URL`: Your Render app URL (e.g., `https://mystory-app.onrender.com`) - **Update this after deployment!**

---

## ✅ **OPTIONAL - Add if You're Using These Features**

### OAuth Login (Google, Facebook, Apple)

**If using Google OAuth:**
```
GOOGLE_CLIENT_ID=your-google-client-id
GOOGLE_CLIENT_SECRET=your-google-client-secret
```

**If using Facebook OAuth:**
```
FACEBOOK_CLIENT_ID=your-facebook-app-id
FACEBOOK_CLIENT_SECRET=your-facebook-app-secret
```

**If using Apple Sign In:**
```
APPLE_CLIENT_ID=com.yourname.mystory.web
APPLE_CLIENT_SECRET=your-jwt-token-here
```

**Important:** After deployment, update OAuth redirect URIs:
- Google: `https://your-app-name.onrender.com/auth/google/callback`
- Facebook: `https://your-app-name.onrender.com/auth/facebook/callback`
- Apple: `https://your-app-name.onrender.com/auth/apple/callback`

### Email (for email verification and password reset)

**If using email features:**
```
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_USER=your-email@gmail.com
SMTP_PASSWORD=your-app-password
SMTP_FROM=your-email@gmail.com
```

### Image Generation Settings (Optional)

**These control how images are generated. Defaults work well, but you can customize:**

```
MODEL_IMAGE=dall-e-3               # Image generation model: "dall-e-3" (default) or "dall-e-2"
                                    # - DALL-E 3: Higher quality, slower, more expensive
                                    # - DALL-E 2: Faster, cheaper, lower quality

IMAGE_SIZE=1024x1024               # Image dimensions (default: 1024x1024)
                                    # For DALL-E 3: "1024x1024", "1792x1024", or "1024x1792"
                                    # For DALL-E 2: "256x256", "512x512", or "1024x1024"

IMAGE_QUALITY=standard             # Quality setting (DALL-E 3 only, default: "standard")
                                    # Options: "standard" (faster, cheaper) or "hd" (higher quality, slower, more expensive)

MODEL_VISION=gpt-4o-mini           # Vision model for analyzing child's appearance (default: gpt-4o-mini)
                                    # Options: "gpt-4o-mini" (cheaper, fast) or "gpt-4o" (more accurate, expensive)

MAX_IMAGE_WORKERS=6                # Number of parallel image generation workers (default: 6)
                                    # Higher = faster generation but more API calls at once
```

**Cost Considerations:**
- `MODEL_IMAGE=dall-e-3` + `IMAGE_QUALITY=hd` = Highest quality, most expensive
- `MODEL_IMAGE=dall-e-3` + `IMAGE_QUALITY=standard` = Good balance (default)
- `MODEL_IMAGE=dall-e-2` = Cheapest option, lower quality
- `MODEL_VISION=gpt-4o-mini` = Cheaper for child analysis (recommended)

---

## ❌ **DON'T ADD - Automatically Handled by Render**

These are automatically set by Render, so **don't add them manually**:

```
DATABASE_URL                      # ✅ Automatically set from PostgreSQL database
PORT                              # ✅ Automatically set by Render
PYTHON_VERSION                    # ✅ Set in render.yaml (3.11.0)
SESSION_COOKIE_SECURE             # ✅ Set in render.yaml (true)
```

---

## ❌ **DON'T ADD - Local Development Only**

These are only for local development with XAMPP/MySQL:

```
DB_HOST=localhost                 # ❌ Local only
DB_PORT=3306                      # ❌ Local only
DB_NAME=mystory                   # ❌ Local only
DB_USER=root                      # ❌ Local only
DB_PASSWORD=                      # ❌ Local only
```

**Why:** Render uses PostgreSQL and provides `DATABASE_URL` automatically.

---

## ❌ **DON'T ADD - Debug/Testing (Local Only)**

These are for local testing and debugging:

```
FORCE_PLACEHOLDER=0               # ❌ Local testing only
SKIP_VISION_API=0                 # ❌ Local testing only
FLASK_RUN_PORT=5000               # ❌ Local only (Render uses PORT)
```

---

## ❌ **DON'T ADD - SSL/Proxy (Usually Not Needed)**

These are for corporate networks/filters. Usually not needed on Render:

```
REQUESTS_CA_BUNDLE=...            # ❌ Usually not needed
SSL_CERT_FILE=...                 # ❌ Usually not needed
HTTPS_PROXY=...                   # ❌ Usually not needed
OPENAI_DISABLE_SSL_VERIFY=0       # ❌ Never use in production
OPENAI_HTTP_TIMEOUT=120           # ❌ Optional, default is fine
```

**Note:** Only add these if you have specific network requirements.

---

## ❌ **DON'T ADD - Storage (Optional for Later)**

These are for cloud storage. You can add later if needed:

```
STORAGE_TYPE=local                # ❌ Default is fine (local storage)
AWS_S3_BUCKET=...                 # ❌ Only if using S3
AWS_ACCESS_KEY_ID=...              # ❌ Only if using S3
AWS_SECRET_ACCESS_KEY=...          # ❌ Only if using S3
GCS_BUCKET=...                     # ❌ Only if using Google Cloud
CLOUDINARY_CLOUD_NAME=...          # ❌ Only if using Cloudinary
```

**Note:** For now, local storage is fine. You can migrate to cloud storage later.

---

## 📋 **Quick Checklist for Render**

### Minimum Required (App will work):
- [ ] `OPENAI_API_KEY`
- [ ] `SECRET_KEY`
- [ ] `APP_URL` (set after deployment)

### If Using OAuth:
- [ ] `GOOGLE_CLIENT_ID` and `GOOGLE_CLIENT_SECRET` (if using Google)
- [ ] `FACEBOOK_CLIENT_ID` and `FACEBOOK_CLIENT_SECRET` (if using Facebook)
- [ ] `APPLE_CLIENT_ID` and `APPLE_CLIENT_SECRET` (if using Apple)

### If Using Email:
- [ ] `SMTP_HOST`, `SMTP_PORT`, `SMTP_USER`, `SMTP_PASSWORD`, `SMTP_FROM`

### Optional:
- [ ] `MODEL_VISION` (default is fine)
- [ ] `MODEL_IMAGE` (default is fine)
- [ ] `IMAGE_SIZE` (default is fine)
- [ ] `MAX_IMAGE_WORKERS` (default is fine)

---

## 🚀 **How to Add Variables in Render**

1. Go to your **Web Service** in Render Dashboard
2. Click **"Environment"** tab
3. Click **"Add Environment Variable"**
4. Enter **Key** and **Value**
5. Click **"Save Changes"**
6. Your service will automatically redeploy

---

## ⚠️ **Important Notes**

1. **Never commit `.env` file** - It contains secrets!
2. **`APP_URL`** - Set this **after** you know your Render URL
3. **OAuth Redirect URIs** - Update these in OAuth provider consoles after deployment
4. **`DATABASE_URL`** - Automatically set by Render, don't add manually
5. **Secrets** - Render marks sensitive variables (like API keys) as "Secret" automatically

---

## 📝 **Example: Minimal Setup**

For a basic deployment, you only need:

```
OPENAI_API_KEY=sk-...
SECRET_KEY=...
APP_URL=https://mystory-app.onrender.com
```

Everything else is optional or automatically handled!

