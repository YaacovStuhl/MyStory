"""
Quick script to check if your .env file is configured correctly for MySQL.
"""

import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

print("=" * 60)
print("Checking .env Configuration for MySQL")
print("=" * 60)

# Check if .env file exists
env_path = os.path.join(os.getcwd(), ".env")
if os.path.exists(env_path):
    print(f"✓ .env file found at: {env_path}")
else:
    print(f"✗ .env file NOT found at: {env_path}")
    print(f"  Expected location: {os.getcwd()}")
    print(f"  Please create .env file in the project root directory")
    exit(1)

print()

# Check DATABASE_URL
database_url = os.getenv("DATABASE_URL")
    if database_url:
        print("✓ DATABASE_URL is set")
        if database_url.startswith("mysql://"):
            print("  ✓ Connection string format is correct (mysql://)")
        else:
            print("  ⚠ Connection string should start with 'mysql://'")
    # Don't print the full URL (contains password)
    if "@" in database_url:
        parts = database_url.split("@")
        if len(parts) > 0:
            print(f"  Connection: {parts[0].split('://')[0]}://***@{parts[1] if len(parts) > 1 else '...'}")
else:
    print("✗ DATABASE_URL is not set")
    print("  Using individual components instead...")
    print()

# Check individual components
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")
db_name = os.getenv("DB_NAME", "mystory")
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "")

print("Database Configuration:")
print(f"  DB_HOST: {db_host}")
print(f"  DB_PORT: {db_port}")
print(f"  DB_NAME: {db_name}")
print(f"  DB_USER: {db_user}")
print(f"  DB_PASSWORD: {'***' if db_password else '✗ NOT SET (THIS IS THE PROBLEM!)'}")

print()
print("=" * 60)

# Validation
issues = []
if not database_url:
    if not db_password:
        issues.append("DB_PASSWORD is missing - MySQL requires a password")
    if db_port != "3306":
        print(f"  ⚠ Port is {db_port} - MySQL default is 3306")
        if db_port == "5432":
            issues.append("Port 5432 is for PostgreSQL, not MySQL. You need MySQL (port 3306)")
        elif db_port == "1433":
            issues.append("Port 1433 is for SQL Server, not MySQL. You need MySQL (port 3306)")

if issues:
    print("\n❌ ISSUES FOUND:")
    for issue in issues:
        print(f"  - {issue}")
    print()
    print("To fix:")
    print("1. If you have AWS RDS PostgreSQL/SQL Server, you need to create a MySQL RDS instance instead")
    print("2. Or use a local MySQL database")
    print("3. Make sure DB_PASSWORD is set in your .env file")
    print()
    print("Example .env configuration for AWS RDS MySQL:")
    print("  DB_HOST=your-mysql-endpoint.region.rds.amazonaws.com")
    print("  DB_PORT=3306")
    print("  DB_NAME=mystory")
    print("  DB_USER=your_username")
    print("  DB_PASSWORD=your_password")
    print()
    print("Or use connection string:")
    print("  DATABASE_URL=mysql://user:password@host:3306/mystory")
else:
    print("\n✓ Configuration looks good!")
    print("  You can now try running: python init_db.py")


