# Troubleshooting Guide

## SSL Certificate Errors (Internet Filters/Proxies)

### Problem: SSL Certificate Verification Failed

**Symptoms:**
- Error: `[SSL: CERTIFICATE_VERIFY_FAILED] certificate verify failed: unable to get local issuer certificate`
- DNS, TCP, and SSL handshake work, but HTTP requests fail
- You have an internet filter, corporate proxy, or security software that intercepts HTTPS

**Cause:**
Your internet filter/proxy uses a "Man-in-the-Middle" (MITM) approach to inspect HTTPS traffic. It intercepts connections and presents its own certificate, which Python doesn't trust by default.

### Solution Options

#### Option 1: Use Filter's Certificate (RECOMMENDED)

1. **Export the filter's certificate:**
   - Open your browser (Chrome/Edge)
   - Go to `chrome://settings/certificates` (or `edge://settings/certificates`)
   - Click on "Authorities" tab
   - Look for your internet filter/security software's certificate (e.g., "ContentKeeper", "Forcepoint", "Blue Coat", etc.)
   - Export it as a `.pem` or `.crt` file
   - Save it to a location like `C:\certs\filter-cert.pem`

2. **Configure the app to use the certificate:**
   - Add to your `.env` file:
     ```
     REQUESTS_CA_BUNDLE=C:\certs\filter-cert.pem
     ```
   - Or use the alternative:
     ```
     SSL_CERT_FILE=C:\certs\filter-cert.pem
     ```

3. **Restart the Flask app**

#### Option 2: Disable SSL Verification (NOT RECOMMENDED - Use Only for Testing)

⚠️ **WARNING:** This disables SSL certificate verification, making your connection vulnerable to man-in-the-middle attacks. Only use this if Option 1 doesn't work and you're in a trusted environment.

1. Add to your `.env` file:
   ```
   OPENAI_DISABLE_SSL_VERIFY=1
   ```

2. Restart the Flask app

3. **Remember to re-enable SSL verification later:**
   ```
   OPENAI_DISABLE_SSL_VERIFY=0
   ```

### Finding Your Filter's Certificate

**Method 1: Browser Certificate Store**
1. Open Chrome/Edge
2. Go to `chrome://settings/certificates` or `edge://settings/certificates`
3. Click "Authorities" tab
4. Look for certificates from your filter/security software
5. Click "Export" and save as PEM format

**Method 2: Windows Certificate Store**
1. Open "Certificate Manager" (`certmgr.msc`)
2. Navigate to "Trusted Root Certification Authorities" > "Certificates"
3. Look for your filter's certificate
4. Right-click > "All Tasks" > "Export"
5. Choose "Base-64 encoded X.509 (.CER)" format

**Method 3: Contact IT Support**
If you're on a corporate network, contact your IT department for:
- The certificate file
- Instructions on where to place it
- Proxy configuration (if needed)

## Connection Errors

If you're seeing `APIConnectionError - Connection error` in your logs, follow these steps:

### 1. Test Your Connection

Visit `http://127.0.0.1:5000/test-connection` in your browser to run diagnostic tests. This will check:
- DNS resolution for api.openai.com
- TCP connectivity to port 443
- SSL handshake
- OpenAI API authentication

### 2. Common Issues and Solutions

#### Issue: Cannot reach OpenAI API

**Symptoms:**
- `APIConnectionError` in logs
- All API calls fail with connection errors
- Test endpoint shows DNS/TCP/SSL failures

**Solutions:**
1. **Check Internet Connection**
   - Ensure you have an active internet connection
   - Try accessing https://api.openai.com in your browser

2. **Firewall/Proxy Settings**
   - If behind a corporate firewall or proxy, you may need to configure proxy settings
   - Add to your `.env` file:
     ```
     HTTPS_PROXY=http://your-proxy:port
     HTTP_PROXY=http://your-proxy:port
     ```
   - If authentication is required:
     ```
     HTTPS_PROXY=http://username:password@your-proxy:port
     ```

3. **SSL Certificate Issues (Corporate Networks)**
   - If you're on a corporate network with custom SSL certificates, you may need to specify the certificate bundle
   - Add to your `.env` file:
     ```
     REQUESTS_CA_BUNDLE=C:\path\to\your\certificate.pem
     SSL_CERT_FILE=C:\path\to\your\certificate.pem
     ```
   - Contact your IT department for the certificate file

4. **Windows Firewall**
   - Check if Windows Firewall is blocking Python
   - Try temporarily disabling the firewall to test
   - Add Python to the firewall exceptions if needed

5. **Antivirus Software**
   - Some antivirus software blocks network connections
   - Try temporarily disabling to test
   - Add Python/app to antivirus exceptions

### 3. API Key Issues

**Symptoms:**
- `AuthenticationError` or `401` errors
- Test endpoint shows API call failures with authentication errors

**Solutions:**
1. Verify your API key is set in `.env`:
   ```
   OPENAI_API_KEY=sk-your-actual-key-here
   ```
2. Make sure the key starts with `sk-` and is not a placeholder
3. Check that your API key has credits/quotas available
4. Verify the key is valid at https://platform.openai.com/api-keys

### 4. Rate Limiting

**Symptoms:**
- `RateLimitError` or `429` errors
- Intermittent failures

**Solutions:**
1. Wait a few minutes and try again
2. Check your OpenAI usage limits at https://platform.openai.com/usage
3. Consider upgrading your OpenAI plan if you've hit rate limits

### 5. Timeout Issues

**Symptoms:**
- Requests timeout before completion
- Slow network connections

**Solutions:**
1. Increase timeout in `.env`:
   ```
   OPENAI_HTTP_TIMEOUT=180
   ```
2. Use a faster internet connection if possible
3. Consider using DALL-E 2 instead of DALL-E 3 (faster but lower quality):
   ```
   MODEL_IMAGE=dall-e-2
   ```

### 6. Skip Vision API (Temporary Workaround)

If the Vision API is causing issues but image generation works, you can skip it:

Add to `.env`:
```
SKIP_VISION_API=1
```

Note: This will still generate images, but they may be less consistent with the child's actual appearance since the app won't analyze the photo first.

### 7. Debug Mode

Enable more detailed logging by setting the log level:

In `app.py`, change:
```python
logging.basicConfig(level=logging.DEBUG, format="[%(levelname)s] %(message)s")
```

This will show full stack traces for errors, which can help diagnose issues.

## Getting Help

If you've tried all the above and still have issues:

1. Check the `/test-connection` endpoint output
2. Review the full error logs
3. Verify your `.env` file configuration
4. Test with a simple OpenAI API call outside of this app
5. Check OpenAI's status page: https://status.openai.com/

## Environment Variables Reference

See `env.sample` for all available configuration options.

Key variables:
- `OPENAI_API_KEY` - Required: Your OpenAI API key
- `MODEL_IMAGE` - Optional: Image generation model (dall-e-3 or dall-e-2)
- `MODEL_VISION` - Optional: Vision model for analyzing photos (gpt-4o-mini or gpt-4o)
- `HTTPS_PROXY` - Optional: Proxy server for network requests
- `REQUESTS_CA_BUNDLE` - Optional: Path to SSL certificate bundle
- `OPENAI_HTTP_TIMEOUT` - Optional: Request timeout in seconds (default: 120)
- `SKIP_VISION_API` - Optional: Set to "1" to skip photo analysis
- `FORCE_PLACEHOLDER` - Optional: Set to "1" to skip OpenAI and use placeholder images

