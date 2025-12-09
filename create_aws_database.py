"""
Script to create the database (SQLite version).
SQLite creates the database file automatically, so this just verifies it works.
"""

import os
from dotenv import load_dotenv
import database

load_dotenv()


def verify_database():
    """Verify SQLite database can be created and accessed."""
    try:
        db_path = database.get_db_path()
        print(f"Database will be created at: {db_path}")
        
        # Try to initialize connection (creates file if needed)
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            cursor.execute("SELECT 1")
            cursor.close()
        
        print("OK Database file created/verified successfully!")
        return True
        
    except Exception as e:
        print(f"X Error: {e}")
        return False


if __name__ == "__main__":
    print("SQLite Database Verification")
    print("=" * 40)
    if verify_database():
        print("\nOK Success! You can now run 'python init_db.py' to create tables.")
    else:
        print("\nX Failed to create database. Please check the errors above.")
