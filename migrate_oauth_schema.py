"""
Migration script to add oauth_id and name fields to users table.
SQLite version - handles schema migrations.
"""

import os
from dotenv import load_dotenv
import database

load_dotenv()


def migrate_users_table():
    """Add oauth_id and name columns to users table if they don't exist."""
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if oauth_id column exists
            cursor.execute("PRAGMA table_info(users)")
            columns = [row[1] for row in cursor.fetchall()]
            
            # Add columns if they don't exist
            if 'oauth_id' not in columns:
                print("Adding oauth_id column...")
                cursor.execute("ALTER TABLE users ADD COLUMN oauth_id TEXT")
            
            if 'name' not in columns:
                print("Adding name column...")
                cursor.execute("ALTER TABLE users ADD COLUMN name TEXT")
            
            # SQLite doesn't support adding unique constraints after table creation
            # But we can check if the constraint exists by checking the table schema
            cursor.execute("SELECT sql FROM sqlite_master WHERE type='table' AND name='users'")
            table_sql = cursor.fetchone()
            if table_sql and 'UNIQUE(oauth_provider, oauth_id)' not in table_sql[0]:
                print("Note: Unique constraint on (oauth_provider, oauth_id) should be in schema.sql")
                print("If needed, recreate the table with the constraint")
            
            conn.commit()
            cursor.close()
            
            print("OK Migration completed successfully!")
            return True
    except Exception as e:
        print(f"X Migration failed: {e}")
        return False


if __name__ == "__main__":
    print("Migrating users table for OAuth support (SQLite)...")
    if migrate_users_table():
        print("\nOK Database is ready for OAuth login!")
    else:
        print("\nX Migration failed. Please check the error messages above.")
