# Quick Fix for SSL Certificate Errors

## If you're getting SSL certificate errors due to an internet filter:

### Quick Solution (Temporary - for testing only):

1. Open your `.env` file
2. Add this line:
   ```
   OPENAI_DISABLE_SSL_VERIFY=1
   ```
3. Restart your Flask app
4. Test again at `http://127.0.0.1:5000/test-connection`

⚠️ **Warning:** This disables SSL verification and is not secure. Use only for testing.

### Better Solution (Recommended):

1. Export your internet filter's certificate (see TROUBLESHOOTING.md for instructions)
2. Save it to `C:\certs\filter-cert.pem` (create the folder if needed)
3. Add to your `.env` file:
   ```
   REQUESTS_CA_BUNDLE=C:\certs\filter-cert.pem
   ```
4. Restart your Flask app

### Common Filter Certificate Locations:

- **Chrome/Edge:** `chrome://settings/certificates` → Authorities tab
- **Windows:** Certificate Manager (`certmgr.msc`) → Trusted Root Certification Authorities
- **Filter Software:** Check your filter's documentation or settings

### After Fixing:

Once SSL is working, you should see:
- ✓ Direct HTTP request successful
- ✓ API call successful

Then your storybook generation should work!


