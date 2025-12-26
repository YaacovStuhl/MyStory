"""
Quick setup script to test local SQL Server Express connection.
"""

import os
from dotenv import load_dotenv
import pyodbc

load_dotenv()


def test_local_sql():
    """Test connection to local SQL Server Express."""
    print("Testing Local SQL Server Express Connection")
    print("=" * 60)
    
    # Common local SQL Server instance names
    instances = [
        "localhost",
        "localhost\\SQLEXPRESS",
        "localhost\\MSSQLSERVER",
        ".\\SQLEXPRESS",
        ".",
    ]
    
    user = os.getenv("DB_USER", "sa")
    password = os.getenv("DB_PASSWORD", "")
    
    if not password:
        print("Please set DB_PASSWORD in .env file")
        return False
    
    available_drivers = pyodbc.drivers()
    sql_drivers = [d for d in available_drivers if 'SQL Server' in d or 'ODBC Driver' in d]
    
    if not sql_drivers:
        print("X No SQL Server ODBC driver found!")
        return False
    
    driver = "ODBC Driver 17 for SQL Server" if "ODBC Driver 17 for SQL Server" in sql_drivers else sql_drivers[0]
    
    print(f"Using driver: {driver}")
    print(f"Testing instances...")
    print()
    
    for instance in instances:
        try:
            conn_str = (
                f"DRIVER={{{driver}}};"
                f"SERVER={instance};"
                f"DATABASE=master;"
                f"UID={user};"
                f"PWD={password};"
                f"TrustServerCertificate=yes;"
                f"Encrypt=no"
            )
            
            print(f"Trying {instance}...", end=" ")
            conn = pyodbc.connect(conn_str, timeout=5)
            print("OK Connected!")
            
            cursor = conn.cursor()
            cursor.execute("SELECT @@VERSION")
            version = cursor.fetchone()[0]
            print(f"SQL Server version: {version[:60]}...")
            
            cursor.close()
            conn.close()
            
            print(f"\nOK Found SQL Server at: {instance}")
            print(f"\nUpdate your .env file:")
            print(f"DB_HOST={instance.replace('localhost', 'localhost').replace('.\\', 'localhost\\')}")
            print(f"DB_PORT=1433")
            print(f"DB_NAME=mystory")
            print(f"DB_USER={user}")
            print(f"DB_PASSWORD={password}")
            print(f"DB_ENCRYPT=no")
            
            return True
            
        except Exception as e:
            print(f"Failed: {str(e)[:50]}")
            continue
    
    print("\nX Could not connect to any local SQL Server instance")
    print("\nPossible reasons:")
    print("1. SQL Server Express is not installed")
    print("2. SQL Server service is not running")
    print("3. Wrong username/password")
    print("4. TCP/IP is not enabled")
    return False


if __name__ == "__main__":
    test_local_sql()

