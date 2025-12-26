"""
Database initialization script.
Run this once to set up the database schema and load initial storylines.
"""

import os
import json
from dotenv import load_dotenv
import database

# Load environment variables
load_dotenv()


def load_storylines_from_config():
    """Load storylines from config files and insert into database."""
    config_dir = "config"
    storylines = []
    
    # Load lrrh.json
    lrrh_path = os.path.join(config_dir, "lrrh.json")
    if os.path.exists(lrrh_path):
        with open(lrrh_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            storylines.append(data)
    
    # Load jatb.json
    jatb_path = os.path.join(config_dir, "jatb.json")
    if os.path.exists(jatb_path):
        with open(jatb_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            storylines.append(data)
    
    return storylines


def main():
    """Initialize database and load storylines."""
    print("Initializing database...")
    
    # Check if DATABASE_URL is set
    database_url = os.getenv("DATABASE_URL")
    if not database_url:
        print("WARNING: DATABASE_URL not set - skipping database initialization")
        print("This is normal if database is not configured yet")
        return
    
    # Check if database is available
    try:
        import database
        if not hasattr(database, 'DB_AVAILABLE') or not database.DB_AVAILABLE:
            print("WARNING: Database module not available - skipping initialization")
            return
    except ImportError:
        print("WARNING: Database module not available - skipping initialization")
        return
    
    # Initialize schema
    try:
        if not database.init_database():
            print("ERROR: Failed to initialize database schema")
            print("This might be normal if tables already exist")
            # Continue anyway - tables might already exist
        else:
            print("OK Database schema initialized")
    except Exception as e:
        print(f"WARNING: Database initialization failed: {e}")
        print("This might be normal if database is not accessible yet")
        return
    
    # Load storylines from config files
    print("\nLoading storylines from config files...")
    storylines = load_storylines_from_config()
    
    for storyline in storylines:
        story_id = storyline["story_id"]
        name = storyline["story_name"]
        gender = storyline["gender"]
        
        # Create pages_json structure matching the config format
        pages_json = {
            "story_id": story_id,
            "story_name": name,
            "gender": gender,
            "pages": storyline["pages"]
        }
        
        if database.create_storyline(story_id, name, gender, pages_json):
            print(f"OK Loaded storyline: {name} ({story_id})")
        else:
            print(f"X Failed to load storyline: {name} ({story_id})")
    
    print("\nOK Database initialization complete!")


if __name__ == "__main__":
    main()

