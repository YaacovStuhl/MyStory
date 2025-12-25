# Apple Sign In Setup - Quick Checklist

Use this checklist to quickly set up Apple Sign In for your app.

## ⚠️ Prerequisites

- [ ] **Apple Developer Account** ($99/year) - Required!
- [ ] Flask app is installed and working
- [ ] Have access to your `.env` file
- [ ] `authlib`, `PyJWT`, and `cryptography` are installed

## ✅ Step-by-Step Checklist

### 1. Apple Developer Account
- [ ] Go to https://developer.apple.com/account/
- [ ] Sign in with Apple ID
- [ ] Verify active Apple Developer Program membership ($99/year)
- [ ] Note your Team ID (top right corner): `________________`

### 2. Create App ID
- [ ] Go to: Certificates, Identifiers & Profiles → Identifiers
- [ ] Click "+" → Select "App IDs" → Continue
- [ ] Select "App" → Continue
- [ ] Description: `________________`
- [ ] Bundle ID: `com.________________.mystory`
- [ ] Check "Sign In with Apple"
- [ ] Click Continue → Register

### 3. Create Services ID
- [ ] Still in Identifiers, click "+" again
- [ ] Select "Services IDs" → Continue
- [ ] Description: `________________`
- [ ] Identifier: `com.________________.mystory.web`
- [ ] Click Continue → Register
- [ ] Click on your Services ID to configure
- [ ] Check "Sign In with Apple" → Click "Configure"
- [ ] Primary App ID: Select the App ID from Step 2
- [ ] Domains: `localhost` (or your domain)
- [ ] Return URLs: `http://localhost:5000/auth/apple/callback`
- [ ] Click Save → Continue → Save
- [ ] **Copy Services ID**: `________________` (this is your CLIENT_ID)

### 4. Create Key
- [ ] Go to: Keys
- [ ] Click "+" to create new key
- [ ] Key Name: `________________`
- [ ] Check "Sign In with Apple"
- [ ] Click "Configure" → Select Primary App ID
- [ ] Click Save → Continue → Register
- [ ] **Download the .p8 file** (you can only download once!)
- [ ] **Note the Key ID**: `________________`

### 5. Get Your Credentials
- [ ] Team ID: `________________` (from top right of Apple Developer)
- [ ] Services ID (Client ID): `________________` (from Step 3)
- [ ] Key ID: `________________` (from Step 4)
- [ ] Private Key File: `________________.p8` (downloaded in Step 4)

### 6. Generate Client Secret
- [ ] Install dependencies: `pip install PyJWT cryptography`
- [ ] Run: `python generate_apple_secret.py`
- [ ] Enter your credentials (or set them in .env first)
- [ ] Copy the generated JWT token: `________________`

### 7. Configure .env File
- [ ] Open `.env` file
- [ ] Add:
  ```env
  APPLE_CLIENT_ID=com.yourname.mystory.web
  APPLE_CLIENT_SECRET=your-generated-jwt-token-here
  ```
- [ ] Replace with your actual values

### 8. Restart App
- [ ] Stop Flask app (Ctrl+C)
- [ ] Restart: `python app.py`

### 9. Test
- [ ] Visit: http://localhost:5000
- [ ] Click "Login with Apple"
- [ ] Sign in with Apple ID
- [ ] Should redirect back and be logged in!

## ❌ Common Issues & Quick Fixes

### "Invalid client" Error
- [ ] Verify APPLE_CLIENT_ID matches Services ID exactly
- [ ] Check client secret JWT token is valid
- [ ] Regenerate JWT token if expired

### "Invalid redirect_uri" Error
- [ ] Check Apple Developer → Services ID → Sign In with Apple config
- [ ] Verify Return URL matches exactly: `http://localhost:5000/auth/apple/callback`
- [ ] No trailing slashes!

### "Invalid client_secret" Error
- [ ] Regenerate JWT token
- [ ] Check token expiration (must be future date)
- [ ] Verify private key file is correct
- [ ] Make sure all JWT claims are correct

### Can't Test on Localhost
- [ ] Apple may restrict localhost in production
- [ ] Consider using ngrok for testing
- [ ] Or test on staging server with real domain

### JWT Generation Fails
- [ ] Verify .p8 key file exists and is readable
- [ ] Check Key ID matches
- [ ] Verify Team ID is correct
- [ ] Ensure Services ID matches exactly
- [ ] Install: `pip install PyJWT cryptography`

## 📝 Important Notes

- **Apple Developer Account Required**: $99/year membership needed
- **Client Secret Expires**: JWT tokens expire after 6 months - regenerate before expiration
- **Localhost Limitations**: Apple may not allow localhost for production apps
- **Never Commit**: Don't commit your .p8 private key file to git!

## 🔗 Quick Links

- Apple Developer Portal: https://developer.apple.com/account/
- Your Services IDs: Certificates, Identifiers & Profiles → Identifiers
- Your Keys: Certificates, Identifiers & Profiles → Keys
- Team ID: Top right corner of Apple Developer portal

## 💡 Tips

- Store your .p8 file securely (never in git!)
- Regenerate client secret before it expires (every 6 months)
- For production, you'll need domain verification
- Consider using environment variables for sensitive data

