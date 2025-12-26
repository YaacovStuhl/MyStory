# CRITICAL FIX: Render Dashboard Configuration

## The Problem

The error `==> Running 'web: gunicorn...'` means Render is executing a command with a `web:` prefix, which is Procfile format. This is coming from your **Render dashboard configuration**, not from `render.yaml`.

## The Solution (Choose One)

### Option 1: Fix Dashboard Start Command (FASTEST)

1. Go to https://dashboard.render.com
2. Click on your **mystory-app** service
3. Go to **Settings** tab
4. Scroll to **Build & Deploy** section
5. Find the **Start Command** field
6. **CURRENT (WRONG):** Probably shows something like:
   ```
   web: gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
   ```
   OR
   ```
   web: cd MyStory && gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
   ```

7. **CHANGE TO (CORRECT):** Remove the `web:` prefix:
   ```
   cd MyStory && gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app
   ```

8. **Save Changes**
9. **Manual Deploy** → **Deploy latest commit**

### Option 2: Use Infrastructure as Code (CLEANEST)

1. **Delete** the existing service in Render dashboard
2. In Render dashboard, click **"New +"** → **"Blueprint"**
3. Connect your GitHub repository
4. Render will automatically detect `render.yaml` and create the service
5. This ensures `render.yaml` is used, not dashboard config

## Why This Happens

- **Manual service creation** → uses dashboard config
- **Blueprint/Infrastructure as Code** → uses `render.yaml`
- If you created the service manually, the dashboard start command overrides `render.yaml`

## Verification

After fixing, the deploy log should show:
```
==> Running 'cd MyStory && gunicorn --worker-class eventlet -w 1 --bind 0.0.0.0:$PORT --timeout 120 app:app'
```

**NOT:**
```
==> Running 'web: gunicorn...'
```

## Build Command (Also Check)

While you're in Settings, also verify **Build Command** is:
```
cd MyStory && pip install -r requirements.txt
```

