# Render Disk Space Fix - Optimize Build Size

## Problem: Build Using 8GB+ Disk Space

Large packages are consuming too much disk space during build:
- `opencv-python` (~67MB) - Required for face detection
- `mediapipe` (~10MB) - Optional, has fallback
- `numpy` (~16MB) - Required
- Build artifacts and temporary files

## Solution: Make Optional Packages Optional

I've made `mediapipe` optional since the code has fallbacks:

### What I Changed

1. **Commented out `mediapipe`** in `requirements.txt`
   - Code will use OpenAI Vision API fallback for hand detection
   - Still works, just slightly less accurate

2. **Already removed `face-recognition`**
   - Code uses OpenCV fallback instead

## Current Required Packages (Can't Remove)

These are essential and must stay:
- `opencv-python` - Required for face detection (no `face-recognition` anymore)
- `numpy` - Required for image processing
- `cryptography` - Required for OAuth (Apple Sign In)
- `psycopg2-binary` - Required for PostgreSQL

## Optional Packages (Can Remove)

- ✅ `mediapipe` - Now optional (OpenAI Vision API fallback)
- ✅ `face-recognition` - Already removed (OpenCV fallback)

## Build Size Reduction

**Before:** ~8GB+ (with `dlib` compilation)
**After:** ~500MB-1GB (without optional packages)

## Should You Upgrade?

**Short answer: No, not yet.**

Try this optimized build first. The free tier should have enough space (~2GB) for the optimized requirements.

**If it still fails:**
- Free tier: ~2GB disk space
- Starter tier: ~10GB disk space ($7/month)
- Standard tier: ~25GB disk space ($25/month)

## Next Steps

1. **Commit and push** the updated `requirements.txt`
2. **Rebuild** on Render
3. **Monitor disk usage** - should be much lower now
4. **If still fails**, then consider upgrading tier

## Alternative: Use Lighter OpenCV

If still having issues, we could try `opencv-python-headless` (no GUI dependencies, smaller):
```
opencv-python-headless>=4.8.0  # Lighter version, no GUI
```

But this shouldn't be necessary with the current optimizations.

