"""
Helper script to get your AWS RDS PostgreSQL endpoint.
This will help you find the correct endpoint to put in your .env file.
"""

import os
from dotenv import load_dotenv

load_dotenv()

print("=" * 70)
print("AWS RDS PostgreSQL Endpoint Finder")
print("=" * 70)
print()
print("To get your PostgreSQL RDS endpoint:")
print()
print("1. Go to AWS Console: https://console.aws.amazon.com/rds/")
print("2. Make sure you're in the correct region (us-east-2)")
print("3. Click on your PostgreSQL database instance")
print("4. Under 'Connectivity & security', find 'Endpoint'")
print("5. Copy the endpoint (it looks like: mystory-postgres.xxxxx.us-east-2.rds.amazonaws.com)")
print()
print("Current .env configuration:")
print(f"  DB_HOST: {os.getenv('DB_HOST', 'NOT SET')}")
print()
print("The endpoint should:")
print("  ✓ End with '.rds.amazonaws.com'")
print("  ✓ Contain your region (e.g., us-east-2)")
print("  ✓ NOT contain 'abc123' (that's a placeholder)")
print()
print("Example of a REAL endpoint:")
print("  mystory-postgres.c9iogokkc7cl.us-east-2.rds.amazonaws.com")
print()
print("If you haven't created the PostgreSQL RDS instance yet:")
print("  See POSTGRESQL_AWS_RDS_SETUP.md for instructions")
print()


