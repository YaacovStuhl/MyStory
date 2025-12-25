# Complete Guide: Setting Up Apple Sign In (OAuth)

This guide will walk you through setting up Apple Sign In for your MyStory application.

## Prerequisites

- **Apple Developer Account** ($99/year) - Required
- Your Flask app running locally (or production URL)
- Access to your `.env` file
- A domain name (for production) or localhost for testing

⚠️ **Important**: Apple Sign In requires an Apple Developer account. You cannot set it up without one.

---

## Step-by-Step Setup

### Step 1: Access Apple Developer Portal

1. Go to: **https://developer.apple.com/account/**
2. Sign in with your Apple ID
3. Make sure you have an active Apple Developer Program membership ($99/year)

### Step 2: Create an App ID

1. In the left sidebar, go to **"Certificates, Identifiers & Profiles"**
2. Click **"Identifiers"** in the left sidebar
3. Click the **"+"** button to create a new identifier
4. Select **"App IDs"** and click **"Continue"**
5. Select **"App"** and click **"Continue"**
6. Fill in:
   - **Description**: "My Story App" (or your app name)
   - **Bundle ID**: Choose a unique identifier (e.g., `com.yourname.mystory`)
7. Scroll down and check **"Sign In with Apple"**
8. Click **"Continue"** then **"Register"**

### Step 3: Create a Services ID

1. Still in **"Identifiers"**, click the **"+"** button again
2. Select **"Services IDs"** and click **"Continue"**
3. Fill in:
   - **Description**: "My Story App Web" (or your web service name)
   - **Identifier**: A unique identifier (e.g., `com.yourname.mystory.web`)
4. Click **"Continue"** then **"Register"**
5. **IMPORTANT**: Click on your newly created Services ID to configure it
6. Check the box for **"Sign In with Apple"**
7. Click **"Configure"** next to "Sign In with Apple"
8. In the configuration:
   - **Primary App ID**: Select the App ID you created in Step 2
   - **Website URLs**:
     - **Domains and Subdomains**: `localhost` (for local testing) or your production domain
     - **Return URLs**: 
       - For local: `http://localhost:5000/auth/apple/callback`
       - For production: `https://your-domain.com/auth/apple/callback`
9. Click **"Save"**, then **"Continue"**, then **"Save"** again

**Note**: For localhost testing, Apple may have restrictions. You might need to use a production domain or use a service like ngrok for testing.

### Step 4: Create a Key for Sign In with Apple

1. In the left sidebar, go to **"Keys"**
2. Click the **"+"** button to create a new key
3. Fill in:
   - **Key Name**: "My Story App Sign In Key" (or any name)
   - Check **"Sign In with Apple"**
4. Click **"Configure"** next to "Sign In with Apple"
5. Select the **Primary App ID** you created in Step 2
6. Click **"Save"**, then **"Continue"**, then **"Register"**
7. **CRITICAL**: Download the key file (`.p8` file) - **You can only download it once!**
8. **Note the Key ID** - you'll need this later

### Step 5: Generate Client Secret (JWT Token)

Apple uses JWT tokens as the client secret, not a simple string. You need to generate this token.

**Option A: Using Python Script (Recommended)**

Create a file `generate_apple_secret.py`:

```python
import jwt
import time
from datetime import datetime, timedelta

# Your Apple credentials
TEAM_ID = "YOUR_TEAM_ID"  # Found in Apple Developer account (top right)
CLIENT_ID = "com.yourname.mystory.web"  # Your Services ID from Step 3
KEY_ID = "YOUR_KEY_ID"  # The Key ID from Step 4
PRIVATE_KEY_PATH = "path/to/your/AuthKey_KEYID.p8"  # The .p8 file from Step 4

# Read the private key
with open(PRIVATE_KEY_PATH, 'r') as f:
    private_key = f.read()

# Create JWT token
headers = {
    "kid": KEY_ID,
    "alg": "ES256"
}

payload = {
    "iss": TEAM_ID,
    "iat": int(time.time()),
    "exp": int(time.time()) + 86400 * 180,  # 6 months validity
    "aud": "https://appleid.apple.com",
    "sub": CLIENT_ID
}

# Generate the token
client_secret = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
print(f"APPLE_CLIENT_SECRET={client_secret}")
```

Run it:
```bash
python generate_apple_secret.py
```

**Option B: Using Online Tool**

You can use online JWT generators, but be cautious with security:
- https://developer.apple.com/documentation/sign_in_with_apple/generate_and_validate_tokens

**Option C: Generate in Your App (Advanced)**

You can generate the token dynamically in your app, but it's more complex.

### Step 6: Get Your Team ID

1. In Apple Developer portal, look at the top right corner
2. Your **Team ID** is displayed there (looks like: `ABC123DEF4`)
3. Write it down - you'll need it for generating the client secret

### Step 7: Configure Your .env File

Add the following to your `.env` file:

```env
# Apple Sign In Configuration
APPLE_CLIENT_ID=com.yourname.mystory.web  # Your Services ID from Step 3
APPLE_CLIENT_SECRET=eyJraWQiOi...  # The JWT token from Step 5

# Optional: If you need to generate the secret dynamically
# APPLE_TEAM_ID=ABC123DEF4  # Your Team ID
# APPLE_KEY_ID=XYZ789  # Your Key ID
# APPLE_PRIVATE_KEY_PATH=path/to/AuthKey_KEYID.p8  # Path to your .p8 file
```

### Step 8: Install Required Dependencies

Make sure you have the required library for JWT:

```bash
pip install PyJWT cryptography
```

Or if using `authlib` (which should already be installed):
```bash
pip install authlib[apple]
```

### Step 9: Restart Your Flask App

1. Stop your Flask app (Ctrl+C)
2. Restart it:
   ```bash
   python app.py
   ```

### Step 10: Test Apple Sign In

1. Visit `http://localhost:5000`
2. Look for the **"Login with Apple"** button
3. Click it
4. You should be redirected to Apple's login page
5. Sign in with your Apple ID
6. After authorizing, you should be redirected back to your app
7. You should now be logged in!

---

## Important Notes

### Localhost Limitations

⚠️ **Apple Sign In has restrictions for localhost**:
- Apple may not allow `localhost` as a return URL in production
- For local testing, consider:
  - Using a production domain with localhost subdomain
  - Using a service like **ngrok** to create a tunnel
  - Testing on a staging server with a real domain

### Client Secret Expiration

- Apple client secrets (JWT tokens) expire after 6 months
- You'll need to regenerate the secret periodically
- Consider implementing automatic token refresh in production

### Domain Verification

For production:
1. You'll need to verify domain ownership
2. Apple will provide a file to upload to your domain
3. Follow Apple's domain verification process

---

## Troubleshooting

### Error: "Invalid client"

**Cause**: Wrong Client ID or Client Secret.

**Solution**:
1. Verify `APPLE_CLIENT_ID` matches your Services ID exactly
2. Check that your client secret JWT token is valid and not expired
3. Regenerate the JWT token if needed

### Error: "Invalid redirect_uri"

**Cause**: The redirect URI doesn't match what's configured in Apple Developer.

**Solution**:
1. Go to Apple Developer → Identifiers → Your Services ID
2. Check "Sign In with Apple" configuration
3. Verify the Return URL matches exactly: `http://localhost:5000/auth/apple/callback`
4. Make sure there are no trailing slashes

### Error: "Invalid client_secret"

**Cause**: The JWT token is malformed or expired.

**Solution**:
1. Regenerate the client secret JWT token
2. Make sure the token includes all required claims:
   - `iss` (Team ID)
   - `iat` (issued at)
   - `exp` (expiration - must be future)
   - `aud` (must be "https://appleid.apple.com")
   - `sub` (must be your Services ID)
3. Verify the private key file is correct

### Error: "redirect_uri_mismatch"

**Cause**: The redirect URI in your code doesn't match Apple's configuration.

**Solution**:
1. Check your app logs for the redirect URI being used
2. Make sure it matches exactly what's in Apple Developer portal
3. For localhost, Apple may require a specific format

### Can't find "Services IDs"

**Solution**:
1. Make sure you're in the correct Apple Developer account
2. Go to: Certificates, Identifiers & Profiles → Identifiers
3. Click the "+" button to create a new identifier
4. Select "Services IDs"

### JWT Token Generation Fails

**Solution**:
1. Verify you have the correct `.p8` key file
2. Check that the Key ID matches
3. Ensure Team ID is correct
4. Make sure the Services ID (CLIENT_ID) matches exactly
5. Check that the token expiration is in the future

---

## Production Setup

When deploying to production:

1. **Update Services ID Configuration**:
   - Add your production domain to "Domains and Subdomains"
   - Add production return URL: `https://your-domain.com/auth/apple/callback`

2. **Domain Verification**:
   - Apple will provide a verification file
   - Upload it to your domain's `.well-known` directory
   - Complete domain verification in Apple Developer portal

3. **Update .env**:
   ```env
   APPLE_CLIENT_ID=com.yourname.mystory.web
   APPLE_CLIENT_SECRET=your-jwt-token-here
   ```

4. **Consider Token Refresh**:
   - Implement automatic JWT token regeneration
   - Tokens expire after 6 months
   - Store the private key securely (never commit to git!)

---

## Security Best Practices

- **Never commit** your `.p8` private key file to version control
- **Store private keys** securely (use environment variables or secure key management)
- **Rotate keys** periodically
- **Regenerate client secrets** before they expire
- **Use HTTPS** in production
- **Keep Team ID and Key ID** secure

---

## Quick Reference

**Apple Developer Portal**: https://developer.apple.com/account/

**Required Redirect URI** (local): `http://localhost:5000/auth/apple/callback`

**Required Redirect URI** (production): `https://your-domain.com/auth/apple/callback`

**Environment Variables Needed**:
- `APPLE_CLIENT_ID` (your Services ID)
- `APPLE_CLIENT_SECRET` (JWT token)

**Optional** (for dynamic token generation):
- `APPLE_TEAM_ID`
- `APPLE_KEY_ID`
- `APPLE_PRIVATE_KEY_PATH`

---

## Still Having Issues?

1. Check the Flask app logs for error messages
2. Verify all identifiers match exactly (case-sensitive)
3. Make sure your Apple Developer account is active
4. Test with a production domain if localhost doesn't work
5. Check Apple's documentation: https://developer.apple.com/sign-in-with-apple/

---

## Alternative: Testing Without Apple Developer Account

If you don't have an Apple Developer account:
- Apple Sign In requires a paid Apple Developer Program membership
- You cannot test Apple Sign In without it
- Consider using Google or Facebook OAuth for testing instead

