"""
Generate Apple Sign In Client Secret (JWT Token)

This script generates the JWT token needed for Apple OAuth client_secret.
Apple requires a JWT token instead of a simple string secret.

Usage:
1. Get your credentials from Apple Developer portal:
   - Team ID (found in top right of Apple Developer account)
   - Services ID (the identifier you created for Sign In with Apple)
   - Key ID (from the key you created)
   - Private Key file (.p8 file you downloaded)

2. Update the variables below or pass them as command line arguments

3. Run: python generate_apple_secret.py

4. Copy the output to your .env file as APPLE_CLIENT_SECRET
"""

import os
import sys
import jwt
import time
from pathlib import Path
from dotenv import load_dotenv

# Load .env if it exists
load_dotenv()

def generate_apple_secret(team_id=None, client_id=None, key_id=None, private_key_path=None):
    """Generate Apple Sign In client secret JWT token."""
    
    # Get values from environment or parameters
    team_id = team_id or os.getenv("APPLE_TEAM_ID")
    client_id = client_id or os.getenv("APPLE_CLIENT_ID")
    key_id = key_id or os.getenv("APPLE_KEY_ID")
    private_key_path = private_key_path or os.getenv("APPLE_PRIVATE_KEY_PATH")
    
    # Validate required parameters
    if not team_id:
        print("ERROR: Team ID is required")
        print("Get it from: https://developer.apple.com/account/ (top right corner)")
        return None
    
    if not client_id:
        print("ERROR: Client ID (Services ID) is required")
        print("This is the Services ID you created in Apple Developer portal")
        return None
    
    if not key_id:
        print("ERROR: Key ID is required")
        print("This is the Key ID from the key you created for Sign In with Apple")
        return None
    
    if not private_key_path:
        print("ERROR: Private key path is required")
        print("This is the path to the .p8 file you downloaded from Apple")
        return None
    
    # Check if private key file exists
    key_path = Path(private_key_path)
    if not key_path.exists():
        print(f"ERROR: Private key file not found: {private_key_path}")
        return None
    
    # Read the private key
    try:
        with open(key_path, 'r') as f:
            private_key = f.read()
    except Exception as e:
        print(f"ERROR: Failed to read private key file: {e}")
        return None
    
    # Create JWT token headers
    headers = {
        "kid": key_id,
        "alg": "ES256"
    }
    
    # Create JWT token payload
    now = int(time.time())
    payload = {
        "iss": team_id,  # Issuer (Team ID)
        "iat": now,  # Issued at
        "exp": now + (86400 * 180),  # Expiration (6 months from now)
        "aud": "https://appleid.apple.com",  # Audience
        "sub": client_id  # Subject (Services ID)
    }
    
    # Generate the JWT token
    try:
        client_secret = jwt.encode(payload, private_key, algorithm="ES256", headers=headers)
        return client_secret
    except Exception as e:
        print(f"ERROR: Failed to generate JWT token: {e}")
        print("Make sure you have PyJWT and cryptography installed:")
        print("  pip install PyJWT cryptography")
        return None


def main():
    """Main function to generate and display the client secret."""
    print("=" * 60)
    print("Apple Sign In - Client Secret Generator")
    print("=" * 60)
    print()
    
    # Check if running with command line arguments
    if len(sys.argv) > 1:
        team_id = sys.argv[1] if len(sys.argv) > 1 else None
        client_id = sys.argv[2] if len(sys.argv) > 2 else None
        key_id = sys.argv[3] if len(sys.argv) > 3 else None
        private_key_path = sys.argv[4] if len(sys.argv) > 4 else None
    else:
        # Interactive mode
        print("Enter your Apple Developer credentials:")
        print("(Press Enter to use values from .env file)")
        print()
        
        team_id = input("Team ID: ").strip() or None
        client_id = input("Client ID (Services ID): ").strip() or None
        key_id = input("Key ID: ").strip() or None
        private_key_path = input("Private Key Path (.p8 file): ").strip() or None
    
    # Generate the secret
    client_secret = generate_apple_secret(team_id, client_id, key_id, private_key_path)
    
    if client_secret:
        print()
        print("=" * 60)
        print("SUCCESS! Generated Apple Client Secret")
        print("=" * 60)
        print()
        print("Add this to your .env file:")
        print()
        print(f"APPLE_CLIENT_SECRET={client_secret}")
        print()
        print("Note: This token expires in 6 months. You'll need to regenerate it.")
        print("=" * 60)
    else:
        print()
        print("=" * 60)
        print("FAILED to generate client secret")
        print("=" * 60)
        print()
        print("Make sure you have:")
        print("1. Team ID from Apple Developer account")
        print("2. Services ID (Client ID) from Apple Developer portal")
        print("3. Key ID from the key you created")
        print("4. Private key file (.p8) downloaded from Apple")
        print()
        print("Install required packages:")
        print("  pip install PyJWT cryptography")
        sys.exit(1)


if __name__ == "__main__":
    main()

