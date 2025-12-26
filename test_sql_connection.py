"""
Test SQL Server connection and diagnose issues.
"""

import os
from dotenv import load_dotenv
import pyodbc

load_dotenv()


def test_connection():
    """Test SQL Server connection with detailed diagnostics."""
    host = os.getenv("DB_HOST")
    port = os.getenv("DB_PORT", "1433")
    database = os.getenv("DB_NAME", "master")
    user = os.getenv("DB_USER")
    password = os.getenv("DB_PASSWORD")
    
    print("=" * 60)
    print("SQL Server Connection Test")
    print("=" * 60)
    print(f"Host: {host}")
    print(f"Port: {port}")
    print(f"Database: {database}")
    print(f"User: {user}")
    print(f"Password: {'*' * len(password) if password else 'NOT SET'}")
    print()
    
    # Check available drivers
    available_drivers = pyodbc.drivers()
    sql_drivers = [d for d in available_drivers if 'SQL Server' in d or 'ODBC Driver' in d]
    print(f"Available SQL Server drivers: {sql_drivers}")
    print()
    
    if not sql_drivers:
        print("X No SQL Server ODBC driver found!")
        return False
    
    # Try each driver
    driver = "ODBC Driver 17 for SQL Server" if "ODBC Driver 17 for SQL Server" in sql_drivers else sql_drivers[0]
    print(f"Using driver: {driver}")
    print()
    
    # Build connection string
    # Try without encryption (helps with internet filters)
    encrypt = os.getenv("DB_ENCRYPT", "no").lower()
    
    conn_str = (
        f"DRIVER={{{driver}}};"
        f"SERVER={host},{port};"
        f"DATABASE={database};"
        f"UID={user};"
        f"PWD={password};"
        f"TrustServerCertificate=yes;"
        f"Encrypt={encrypt}"
    )
    
    print("Connection string (password hidden):")
    print(conn_str.replace(password, "***"))
    print()
    
    # Test connection
    print("Attempting connection...")
    try:
        conn = pyodbc.connect(conn_str, timeout=10)
        print("OK Connection successful!")
        
        cursor = conn.cursor()
        cursor.execute("SELECT @@VERSION")
        version = cursor.fetchone()[0]
        print(f"SQL Server version: {version[:50]}...")
        
        cursor.close()
        conn.close()
        return True
        
    except pyodbc.OperationalError as e:
        print(f"X Operational Error: {e}")
        print("\nThis usually means:")
        print("1. Database is not publicly accessible (set to 'No' in AWS)")
        print("2. Security group doesn't allow port 1433 from your IP")
        print("3. Firewall is blocking the connection")
        print("4. Wrong port number (should be 1433 for SQL Server)")
        return False
        
    except pyodbc.InterfaceError as e:
        print(f"X Interface Error: {e}")
        print("\nThis usually means:")
        print("1. Wrong driver name")
        print("2. Connection string format issue")
        return False
        
    except Exception as e:
        print(f"X Error: {type(e).__name__}: {e}")
        return False


if __name__ == "__main__":
    if test_connection():
        print("\nOK Connection test passed! You can proceed with database setup.")
    else:
        print("\nX Connection test failed. Please fix the issues above.")
        print("\nNext steps:")
        print("1. In AWS RDS: Set 'Publicly accessible' to 'Yes'")
        print("2. In AWS EC2: Add security group rule for port 1433 from your IP")
        print("3. Wait 5-10 minutes for changes to apply")
        print("4. Run this test again")

