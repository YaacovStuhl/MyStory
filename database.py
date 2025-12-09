"""
Database connection and helper functions for SQLite.
File-based database - no server required, works offline.
"""

import os
import json
import logging
import sqlite3
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from datetime import datetime

# Database file path
_db_path: Optional[str] = None


def get_db_path() -> str:
    """Get SQLite database file path."""
    global _db_path
    
    if _db_path:
        return _db_path
    
    # Get from environment or use default
    db_path = os.getenv("DB_PATH", "mystory.db")
    
    # Make path absolute
    if not os.path.isabs(db_path):
        db_path = os.path.join(os.getcwd(), db_path)
    
    _db_path = db_path
    return _db_path


def init_connection():
    """Initialize SQLite connection (creates database file if it doesn't exist)."""
    db_path = get_db_path()
    # Create directory if needed
    os.makedirs(os.path.dirname(db_path) if os.path.dirname(db_path) else '.', exist_ok=True)
    return db_path


@contextmanager
def get_db_connection():
    """Get a database connection (context manager)."""
    db_path = init_connection()
    conn = None
    try:
        conn = sqlite3.connect(db_path, timeout=30.0)
        conn.row_factory = sqlite3.Row  # Enable dict-like access
        # Enable foreign keys
        conn.execute("PRAGMA foreign_keys = ON")
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"[db] Database error: {e}")
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_cursor():
    """Get a database cursor (context manager)."""
    with get_db_connection() as conn:
        cursor = conn.cursor()
        try:
            yield cursor
        finally:
            cursor.close()


def init_database():
    """Initialize database schema by running schema.sql."""
    try:
        with open("schema.sql", "r", encoding="utf-8") as f:
            schema_sql = f.read()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Execute schema SQL (SQLite can handle multiple statements)
            cursor.executescript(schema_sql)
            conn.commit()
            cursor.close()
        
        logging.info("[db] Database schema initialized successfully")
        return True
    except FileNotFoundError:
        logging.error("[db] schema.sql not found")
        return False
    except Exception as e:
        logging.error(f"[db] Failed to initialize database: {e}")
        return False


# -----------------------------------------------------------------------------
# User operations
# -----------------------------------------------------------------------------

def create_user(email: str, oauth_provider: Optional[str] = None, oauth_id: Optional[str] = None, name: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new user."""
    try:
        with get_db_cursor() as cursor:
            # SQLite INSERT OR REPLACE for upsert
            cursor.execute("""
                INSERT INTO users (email, oauth_provider, oauth_id, name)
                VALUES (?, ?, ?, ?)
                ON CONFLICT(email) DO UPDATE SET
                    oauth_provider = COALESCE(EXCLUDED.oauth_provider, oauth_provider),
                    oauth_id = COALESCE(EXCLUDED.oauth_id, oauth_id),
                    name = COALESCE(EXCLUDED.name, name)
            """, (email, oauth_provider, oauth_id, name))
            
            # Get the user
            cursor.execute(
                "SELECT user_id, email, oauth_provider, oauth_id, name, created_at FROM users WHERE email = ?",
                (email,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to create user: {e}")
        return None


def get_user_by_oauth(oauth_provider: str, oauth_id: str) -> Optional[Dict[str, Any]]:
    """Get user by OAuth provider and ID."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, oauth_provider, oauth_id, name, created_at FROM users WHERE oauth_provider = ? AND oauth_id = ?",
                (oauth_provider, oauth_id)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to get user by OAuth: {e}")
        return None


def link_oauth_account(user_id: int, oauth_provider: str, oauth_id: str) -> bool:
    """Link an OAuth account to an existing user (account linking)."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET oauth_provider = ?, oauth_id = ? WHERE user_id = ?",
                (oauth_provider, oauth_id, user_id)
            )
            return True
    except Exception as e:
        logging.error(f"[db] Failed to link OAuth account: {e}")
        return False


def get_user_by_email(email: str) -> Optional[Dict[str, Any]]:
    """Get user by email."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, oauth_provider, oauth_id, name, created_at FROM users WHERE email = ?",
                (email,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to get user: {e}")
        return None


def get_user_by_id(user_id: int) -> Optional[Dict[str, Any]]:
    """Get user by ID."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, oauth_provider, oauth_id, name, created_at FROM users WHERE user_id = ?",
                (user_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to get user: {e}")
        return None


# -----------------------------------------------------------------------------
# Storyline operations
# -----------------------------------------------------------------------------

def create_storyline(story_id: str, name: str, gender: str, pages_json: Dict[str, Any]) -> bool:
    """Create or update a storyline."""
    try:
        with get_db_cursor() as cursor:
            pages = pages_json.get("pages", [])
            json_str = json.dumps(pages_json)
            cursor.execute("""
                INSERT INTO storylines (story_id, name, gender, pages, pages_json)
                VALUES (?, ?, ?, ?, ?)
                ON CONFLICT(story_id) DO UPDATE SET
                    name = EXCLUDED.name,
                    gender = EXCLUDED.gender,
                    pages = EXCLUDED.pages,
                    pages_json = EXCLUDED.pages_json
            """, (story_id, name, gender, len(pages), json_str))
            return True
    except Exception as e:
        logging.error(f"[db] Failed to create storyline: {e}")
        return False


def get_storyline(story_id: str) -> Optional[Dict[str, Any]]:
    """Get storyline by ID."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT story_id, name, gender, pages, pages_json FROM storylines WHERE story_id = ?",
                (story_id,)
            )
            row = cursor.fetchone()
            if row:
                data = dict(row)
                # Parse JSON if it's a string
                if isinstance(data.get("pages_json"), str):
                    data["pages_json"] = json.loads(data["pages_json"])
                return data
            return None
    except Exception as e:
        logging.error(f"[db] Failed to get storyline: {e}")
        return None


def get_storyline_by_gender(gender: str) -> Optional[Dict[str, Any]]:
    """Get storyline by gender (girl -> lrrh, boy -> jatb)."""
    story_id = "lrrh" if gender.lower() in ("female", "girl") else "jatb"
    return get_storyline(story_id)


# -----------------------------------------------------------------------------
# Book operations
# -----------------------------------------------------------------------------

def create_book(user_id: int, story_id: str, child_name: str, pdf_path: str) -> Optional[Dict[str, Any]]:
    """Create a new book record."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute("""
                INSERT INTO books (user_id, story_id, child_name, pdf_path)
                VALUES (?, ?, ?, ?)
            """, (user_id, story_id, child_name, pdf_path))
            
            book_id = cursor.lastrowid
            
            # Fetch the created book
            cursor.execute(
                "SELECT book_id, user_id, story_id, child_name, pdf_path, created_at FROM books WHERE book_id = ?",
                (book_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to create book: {e}")
        return None


def get_book(book_id: int) -> Optional[Dict[str, Any]]:
    """Get book by ID."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT book_id, user_id, story_id, child_name, pdf_path, created_at FROM books WHERE book_id = ?",
                (book_id,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to get book: {e}")
        return None


def get_user_books(user_id: int, limit: int = 50) -> List[Dict[str, Any]]:
    """Get all books for a user."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT book_id, user_id, story_id, child_name, pdf_path, created_at
                FROM books
                WHERE user_id = ?
                ORDER BY created_at DESC
                LIMIT ?
                """,
                (user_id, limit)
            )
            rows = cursor.fetchall()
            if rows:
                return [dict(row) for row in rows]
            return []
    except Exception as e:
        logging.error(f"[db] Failed to get user books: {e}")
        return []


# -----------------------------------------------------------------------------
# Log operations
# -----------------------------------------------------------------------------

def create_log(user_id: Optional[int], level: str, message: str) -> bool:
    """Create a log entry."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "INSERT INTO logs (user_id, level, message) VALUES (?, ?, ?)",
                (user_id, level.upper(), message)
            )
            return True
    except Exception as e:
        logging.error(f"[db] Failed to create log: {e}")
        return False


def get_logs(user_id: Optional[int] = None, level: Optional[str] = None, limit: int = 100) -> List[Dict[str, Any]]:
    """Get logs with optional filters."""
    try:
        with get_db_cursor() as cursor:
            query = "SELECT log_id, user_id, level, message, timestamp FROM logs WHERE 1=1"
            params = []
            
            if user_id is not None:
                query += " AND user_id = ?"
                params.append(user_id)
            
            if level:
                query += " AND level = ?"
                params.append(level.upper())
            
            query += " ORDER BY timestamp DESC LIMIT ?"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            if rows:
                return [dict(row) for row in rows]
            return []
    except Exception as e:
        logging.error(f"[db] Failed to get logs: {e}")
        return []
