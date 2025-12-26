"""
Migration script to add oauth_id and name fields to users table (MySQL version).
Run this if your database was created before OAuth support was added.
"""

import os
from dotenv import load_dotenv
import database

load_dotenv()


def check_column_exists(cursor, table_name, column_name):
    """Check if a column exists in a MySQL table."""
    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM INFORMATION_SCHEMA.COLUMNS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = %s 
        AND COLUMN_NAME = %s
    """, (table_name, column_name))
    result = cursor.fetchone()
    # Handle both dict and tuple results
    if isinstance(result, dict):
        return result.get('cnt', 0) > 0
    else:
        return (result[0] if result else 0) > 0


def check_index_exists(cursor, table_name, index_name):
    """Check if an index exists in a MySQL table."""
    cursor.execute("""
        SELECT COUNT(*) as cnt
        FROM INFORMATION_SCHEMA.STATISTICS 
        WHERE TABLE_SCHEMA = DATABASE() 
        AND TABLE_NAME = %s 
        AND INDEX_NAME = %s
    """, (table_name, index_name))
    result = cursor.fetchone()
    # Handle both dict and tuple results
    if isinstance(result, dict):
        return result.get('cnt', 0) > 0
    else:
        return (result[0] if result else 0) > 0


def migrate_users_table():
    """Add oauth_id and name columns to users table if they don't exist."""
    try:
        with database.get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Check if oauth_id column exists
            if not check_column_exists(cursor, 'users', 'oauth_id'):
                print("Adding oauth_id column...")
                cursor.execute("ALTER TABLE users ADD COLUMN oauth_id VARCHAR(255) AFTER oauth_provider")
                print("✓ oauth_id column added")
            else:
                print("✓ oauth_id column already exists")
            
            # Check if name column exists
            if not check_column_exists(cursor, 'users', 'name'):
                print("Adding name column...")
                cursor.execute("ALTER TABLE users ADD COLUMN name VARCHAR(255) AFTER oauth_id")
                print("✓ name column added")
            else:
                print("✓ name column already exists")
            
            # Check if unique constraint exists
            if not check_index_exists(cursor, 'users', 'unique_oauth'):
                print("Adding unique constraint on (oauth_provider, oauth_id)...")
                try:
                    cursor.execute("""
                        ALTER TABLE users 
                        ADD UNIQUE KEY unique_oauth (oauth_provider, oauth_id)
                    """)
                    print("✓ unique constraint added")
                except Exception as e:
                    # Constraint might fail if there are duplicate NULL values
                    if "Duplicate" in str(e) or "duplicate" in str(e).lower():
                        print("⚠ Warning: Could not add unique constraint due to existing data")
                        print("  You may need to clean up duplicate NULL values first")
                    else:
                        raise
            else:
                print("✓ unique_oauth constraint already exists")
            
            conn.commit()
            cursor.close()
            
            print("\n✓ Migration completed successfully!")
            return True
    except Exception as e:
        print(f"\n✗ Migration failed: {e}")
        import traceback
        traceback.print_exc()
        return False


if __name__ == "__main__":
    print("=" * 60)
    print("Migrating users table for OAuth support (MySQL)")
    print("=" * 60)
    print()
    
    if migrate_users_table():
        print("\n" + "=" * 60)
        print("✓ Database is ready for OAuth login!")
        print("=" * 60)
    else:
        print("\n" + "=" * 60)
        print("✗ Migration failed. Please check the error messages above.")
        print("=" * 60)
        print("\nNote: If columns already exist, this is normal.")
        print("You can verify by checking your database schema.")

