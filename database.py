"""
Database connection and helper functions for MySQL and PostgreSQL.
Supports both databases with auto-detection based on DATABASE_URL.
"""

import os
import json
import logging
from typing import Optional, Dict, Any, List
from contextlib import contextmanager
from datetime import datetime

# Try to import database adapters
try:
    import pymysql
    from pymysql.cursors import DictCursor
    MYSQL_AVAILABLE = True
except ImportError:
    MYSQL_AVAILABLE = False
    pymysql = None
    DictCursor = None

try:
    import psycopg2
    from psycopg2.extras import RealDictCursor
    POSTGRESQL_AVAILABLE = True
except ImportError:
    POSTGRESQL_AVAILABLE = False
    psycopg2 = None
    RealDictCursor = None

# Connection configuration cache
_db_config: Optional[Dict[str, Any]] = None
_db_type: Optional[str] = None  # 'mysql' or 'postgresql'


def detect_database_type() -> str:
    """Detect database type from DATABASE_URL or environment variables."""
    global _db_type
    
    if _db_type:
        return _db_type
    
    database_url = os.getenv("DATABASE_URL", "")
    
    if database_url.startswith("postgresql://") or database_url.startswith("postgres://"):
        _db_type = "postgresql"
        return _db_type
    elif database_url.startswith("mysql://"):
        _db_type = "mysql"
        return _db_type
    
    # Check if we're in production - if so, default to PostgreSQL (Render uses PostgreSQL)
    is_production = (
        os.getenv("RENDER") is not None or  # Render.com
        os.getenv("DYNO") is not None or    # Heroku
        os.getenv("PORT") is not None        # Generic production indicator
    )
    
    if is_production:
        # Render uses PostgreSQL by default
        _db_type = "postgresql"
        return _db_type
    
    # Check individual components (for local development only)
    db_host = os.getenv("DB_HOST", "localhost")
    db_port = int(os.getenv("DB_PORT", "3306"))
    
    # PostgreSQL default port is 5432
    if db_port == 5432:
        _db_type = "postgresql"
    else:
        _db_type = "mysql"
    
    return _db_type


def get_db_config() -> Dict[str, Any]:
    """Get database configuration from environment variables."""
    global _db_config
    
    if _db_config:
        return _db_config
    
    # Check if we're in a production environment (Render, Heroku, etc.)
    is_production = (
        os.getenv("RENDER") is not None or  # Render.com
        os.getenv("DYNO") is not None or    # Heroku
        os.getenv("PORT") is not None        # Generic production indicator
    )
    
    db_type = detect_database_type()
    
    # Support DATABASE_URL (connection string) - preferred method
    database_url = os.getenv("DATABASE_URL")
    if database_url:
        _db_config = {"dsn": database_url, "type": db_type}
        return _db_config
    
    # In production, DATABASE_URL should be set
    if is_production:
        error_msg = (
            "DATABASE_URL environment variable is not set. "
            "On Render, make sure you have:\n"
            "1. Created a PostgreSQL database service\n"
            "2. Linked it to your web service in render.yaml or dashboard\n"
            "3. The database service name matches 'mystory-db' in render.yaml"
        )
        logging.error(f"[db] {error_msg}")
        raise ValueError(error_msg)
    
    # Support individual components (for local development only)
    if db_type == "postgresql":
        _db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "5432")),
            "database": os.getenv("DB_NAME", "mystory"),
            "user": os.getenv("DB_USER", "postgres"),
            "password": os.getenv("DB_PASSWORD", ""),
            "type": "postgresql"
        }
    else:  # MySQL
        _db_config = {
            "host": os.getenv("DB_HOST", "localhost"),
            "port": int(os.getenv("DB_PORT", "3306")),
            "database": os.getenv("DB_NAME", "mystory"),
            "user": os.getenv("DB_USER", "root"),
            "password": os.getenv("DB_PASSWORD", ""),
            "charset": "utf8mb4",
            "cursorclass": DictCursor,
            "type": "mysql"
        }
    
    return _db_config


@contextmanager
def get_db_connection():
    """Get a database connection (context manager)."""
    try:
        config = get_db_config()
    except ValueError as e:
        # Production environment without DATABASE_URL
        logging.error(f"[db] {e}")
        raise
    
    db_type = config.get("type", detect_database_type())
    conn = None
    
    try:
        if "dsn" in config:
            # Use connection string
            dsn = config["dsn"]
            if db_type == "postgresql":
                if not POSTGRESQL_AVAILABLE:
                    raise ImportError("psycopg2-binary is required for PostgreSQL. Install with: pip install psycopg2-binary")
                conn = psycopg2.connect(dsn)
            else:  # MySQL
                if not MYSQL_AVAILABLE:
                    raise ImportError("PyMySQL is required for MySQL. Install with: pip install PyMySQL")
                # Parse MySQL connection string
                import urllib.parse
                mysql_dsn = dsn
                if mysql_dsn.startswith("mysql://"):
                    mysql_dsn = mysql_dsn.replace("mysql://", "http://")
                parsed = urllib.parse.urlparse(mysql_dsn)
                conn = pymysql.connect(
                    host=parsed.hostname or "localhost",
                    port=parsed.port or 3306,
                    user=parsed.username or "root",
                    password=parsed.password or "",
                    database=parsed.path.lstrip("/") if parsed.path else "mystory",
                    charset="utf8mb4",
                    cursorclass=DictCursor,
                    autocommit=False
                )
        else:
            # Use individual components
            if db_type == "postgresql":
                if not POSTGRESQL_AVAILABLE:
                    raise ImportError("psycopg2-binary is required for PostgreSQL. Install with: pip install psycopg2-binary")
                conn = psycopg2.connect(
                    host=config["host"],
                    port=config["port"],
                    database=config["database"],
                    user=config["user"],
                    password=config["password"]
                )
            else:  # MySQL
                if not MYSQL_AVAILABLE:
                    raise ImportError("PyMySQL is required for MySQL. Install with: pip install PyMySQL")
                conn = pymysql.connect(
                    host=config["host"],
                    port=config["port"],
                    database=config["database"],
                    user=config["user"],
                    password=config["password"],
                    charset=config.get("charset", "utf8mb4"),
                    cursorclass=config.get("cursorclass", DictCursor),
                    autocommit=False
                )
        
        yield conn
        conn.commit()
    except Exception as e:
        if conn:
            conn.rollback()
        logging.error(f"[db] Database error: {e}")
        logging.error("[db] Please check your database configuration in .env file")
        raise
    finally:
        if conn:
            conn.close()


@contextmanager
def get_db_cursor():
    """Get a database cursor (context manager)."""
    config = get_db_config()
    db_type = config.get("type", detect_database_type())
    
    with get_db_connection() as conn:
        if db_type == "postgresql":
            cursor = conn.cursor(cursor_factory=RealDictCursor)
        else:  # MySQL
            cursor = conn.cursor()
        
        try:
            yield cursor
        finally:
            cursor.close()


def get_db_type() -> str:
    """Get the current database type."""
    return detect_database_type()


def init_database():
    """Initialize database schema by running schema.sql."""
    db_type = detect_database_type()
    
    # Choose appropriate schema file
    schema_file = "schema_postgresql.sql" if db_type == "postgresql" else "schema.sql"
    
    try:
        with open(schema_file, "r", encoding="utf-8") as f:
            schema_sql = f.read()
        
        with get_db_connection() as conn:
            cursor = conn.cursor()
            
            # Execute schema SQL
            # PostgreSQL and MySQL handle multi-statement execution differently
            if db_type == "postgresql":
                # PostgreSQL: Execute as single statement (psycopg2 handles it)
                cursor.execute(schema_sql)
            else:
                # MySQL: Split by semicolon and execute one at a time
                statements = []
                current_statement = []
                
                for line in schema_sql.split('\n'):
                    # Remove inline comments
                    if '--' in line:
                        line = line[:line.index('--')]
                    line = line.strip()
                    
                    if line:
                        current_statement.append(line)
                        if line.endswith(';'):
                            statement = ' '.join(current_statement).rstrip(';').strip()
                            if statement:
                                statements.append(statement)
                            current_statement = []
                
                for statement in statements:
                    if statement:
                        try:
                            cursor.execute(statement)
                        except Exception as e:
                            error_str = str(e).lower()
                            if "already exists" in error_str or "duplicate" in error_str:
                                logging.debug(f"[db] Table/index already exists, skipping: {statement[:50]}...")
                            else:
                                logging.warning(f"[db] Statement execution warning: {e}")
            
            conn.commit()
            cursor.close()
        
        logging.info(f"[db] Database schema initialized successfully ({db_type})")
        return True
    except FileNotFoundError:
        logging.error(f"[db] {schema_file} not found")
        return False
    except Exception as e:
        logging.error(f"[db] Failed to initialize database: {e}")
        return False


# -----------------------------------------------------------------------------
# User operations
# -----------------------------------------------------------------------------

def create_user(email: str, oauth_provider: Optional[str] = None, oauth_id: Optional[str] = None, name: Optional[str] = None, password_hash: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new user."""
    db_type = detect_database_type()
    
    try:
        with get_db_cursor() as cursor:
            if db_type == "postgresql":
                # PostgreSQL: ON CONFLICT
                cursor.execute("""
                    INSERT INTO users (email, oauth_provider, oauth_id, name, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (email) DO UPDATE SET
                        oauth_provider = COALESCE(EXCLUDED.oauth_provider, users.oauth_provider),
                        oauth_id = COALESCE(EXCLUDED.oauth_id, users.oauth_id),
                        name = COALESCE(EXCLUDED.name, users.name),
                        password_hash = COALESCE(EXCLUDED.password_hash, users.password_hash)
                """, (email, oauth_provider, oauth_id, name, password_hash))
            else:
                # MySQL: ON DUPLICATE KEY UPDATE
                cursor.execute("""
                    INSERT INTO users (email, oauth_provider, oauth_id, name, password_hash)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        oauth_provider = COALESCE(VALUES(oauth_provider), oauth_provider),
                        oauth_id = COALESCE(VALUES(oauth_id), oauth_id),
                        name = COALESCE(VALUES(name), name),
                        password_hash = COALESCE(VALUES(password_hash), password_hash)
                """, (email, oauth_provider, oauth_id, name, password_hash))
            
            # Get the user
            cursor.execute(
                "SELECT user_id, email, oauth_provider, oauth_id, name, password_hash, email_verified, created_at FROM users WHERE email = %s",
                (email,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to create user: {e}")
        return None


def create_user_with_password(email: str, password_hash: str, name: Optional[str] = None, verification_token: Optional[str] = None, verification_expires: Optional[datetime] = None) -> Optional[Dict[str, Any]]:
    """Create a new user with password (for email/password registration)."""
    db_type = detect_database_type()
    
    try:
        with get_db_cursor() as cursor:
            if db_type == "postgresql":
                # PostgreSQL: Use RETURNING to get the ID
                cursor.execute("""
                    INSERT INTO users (email, password_hash, name, email_verified, verification_token, verification_token_expires)
                    VALUES (%s, %s, %s, FALSE, %s, %s)
                    RETURNING user_id
                """, (email, password_hash, name, verification_token, verification_expires))
                result = cursor.fetchone()
                user_id = result['user_id'] if result else None
            else:
                # MySQL: Use lastrowid
                cursor.execute("""
                    INSERT INTO users (email, password_hash, name, email_verified, verification_token, verification_token_expires)
                    VALUES (%s, %s, %s, FALSE, %s, %s)
                """, (email, password_hash, name, verification_token, verification_expires))
                user_id = cursor.lastrowid
            
            if user_id:
                # Get the created user
                cursor.execute(
                    "SELECT user_id, email, password_hash, name, email_verified, verification_token, created_at FROM users WHERE user_id = %s",
                    (user_id,)
                )
                row = cursor.fetchone()
                if row:
                    return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to create user with password: {e}")
        return None


def get_user_by_email_and_password(email: str, password_hash: str) -> Optional[Dict[str, Any]]:
    """Get user by email and verify password hash (for login)."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, password_hash, name, email_verified, oauth_provider, oauth_id, created_at FROM users WHERE email = %s AND password_hash = %s",
                (email, password_hash)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to get user by email and password: {e}")
        return None


def update_user_verification(user_id: int, verified: bool = True) -> bool:
    """Update user email verification status."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET email_verified = %s, verification_token = NULL, verification_token_expires = NULL WHERE user_id = %s",
                (verified, user_id)
            )
            return True
    except Exception as e:
        logging.error(f"[db] Failed to update user verification: {e}")
        return False


def set_verification_token(user_id: int, token: str, expires: datetime) -> bool:
    """Set email verification token for user."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET verification_token = %s, verification_token_expires = %s WHERE user_id = %s",
                (token, expires, user_id)
            )
            return True
    except Exception as e:
        logging.error(f"[db] Failed to set verification token: {e}")
        return False


def get_user_by_verification_token(token: str) -> Optional[Dict[str, Any]]:
    """Get user by verification token."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, password_hash, name, email_verified, verification_token, verification_token_expires, created_at FROM users WHERE verification_token = %s AND verification_token_expires > NOW()",
                (token,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to get user by verification token: {e}")
        return None


def set_password_reset_token(user_id: int, token: str, expires: datetime) -> bool:
    """Set password reset token for user."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET reset_token = %s, reset_token_expires = %s WHERE user_id = %s",
                (token, expires, user_id)
            )
            return True
    except Exception as e:
        logging.error(f"[db] Failed to set password reset token: {e}")
        return False


def get_user_by_reset_token(token: str) -> Optional[Dict[str, Any]]:
    """Get user by password reset token."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, password_hash, name, reset_token, reset_token_expires, created_at FROM users WHERE reset_token = %s AND reset_token_expires > NOW()",
                (token,)
            )
            row = cursor.fetchone()
            if row:
                return dict(row)
            return None
    except Exception as e:
        logging.error(f"[db] Failed to get user by reset token: {e}")
        return None


def update_user_password(user_id: int, password_hash: str) -> bool:
    """Update user password and clear reset token."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "UPDATE users SET password_hash = %s, reset_token = NULL, reset_token_expires = NULL WHERE user_id = %s",
                (password_hash, user_id)
            )
            return True
    except Exception as e:
        logging.error(f"[db] Failed to update user password: {e}")
        return False


def get_user_by_oauth(oauth_provider: str, oauth_id: str) -> Optional[Dict[str, Any]]:
    """Get user by OAuth provider and ID."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "SELECT user_id, email, oauth_provider, oauth_id, name, created_at FROM users WHERE oauth_provider = %s AND oauth_id = %s",
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
                "UPDATE users SET oauth_provider = %s, oauth_id = %s WHERE user_id = %s",
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
                "SELECT user_id, email, password_hash, oauth_provider, oauth_id, name, email_verified, created_at FROM users WHERE email = %s",
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
                "SELECT user_id, email, password_hash, oauth_provider, oauth_id, name, email_verified, created_at FROM users WHERE user_id = %s",
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
    db_type = detect_database_type()
    
    try:
        with get_db_cursor() as cursor:
            pages = pages_json.get("pages", [])
            json_str = json.dumps(pages_json)
            
            if db_type == "postgresql":
                # PostgreSQL: ON CONFLICT
                cursor.execute("""
                    INSERT INTO storylines (story_id, name, gender, pages, pages_json)
                    VALUES (%s, %s, %s, %s, %s)
                    ON CONFLICT (story_id) DO UPDATE SET
                        name = EXCLUDED.name,
                        gender = EXCLUDED.gender,
                        pages = EXCLUDED.pages,
                        pages_json = EXCLUDED.pages_json
                """, (story_id, name, gender, len(pages), json_str))
            else:
                # MySQL: ON DUPLICATE KEY UPDATE
                cursor.execute("""
                    INSERT INTO storylines (story_id, name, gender, pages, pages_json)
                    VALUES (%s, %s, %s, %s, %s)
                    ON DUPLICATE KEY UPDATE
                        name = VALUES(name),
                        gender = VALUES(gender),
                        pages = VALUES(pages),
                        pages_json = VALUES(pages_json)
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
                "SELECT story_id, name, gender, pages, pages_json FROM storylines WHERE story_id = %s",
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

def create_book(user_id: int, story_id: str, child_name: str, pdf_path: str, thumbnail_path: Optional[str] = None) -> Optional[Dict[str, Any]]:
    """Create a new book record with metadata."""
    db_type = detect_database_type()
    
    try:
        with get_db_cursor() as cursor:
            if db_type == "postgresql":
                # PostgreSQL: Use RETURNING
                cursor.execute("""
                    INSERT INTO books (user_id, story_id, child_name, pdf_path, thumbnail_path, generation_date)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                    RETURNING book_id
                """, (user_id, story_id, child_name, pdf_path, thumbnail_path))
                result = cursor.fetchone()
                book_id = result['book_id'] if result else None
            else:
                # MySQL: Use lastrowid
                cursor.execute("""
                    INSERT INTO books (user_id, story_id, child_name, pdf_path, thumbnail_path, generation_date)
                    VALUES (%s, %s, %s, %s, %s, NOW())
                """, (user_id, story_id, child_name, pdf_path, thumbnail_path))
                book_id = cursor.lastrowid
            
            if book_id:
                # Fetch the created book
                cursor.execute(
                    "SELECT book_id, user_id, story_id, child_name, pdf_path, thumbnail_path, generation_date, created_at FROM books WHERE book_id = %s",
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
                "SELECT book_id, user_id, story_id, child_name, pdf_path, thumbnail_path, generation_date, created_at FROM books WHERE book_id = %s",
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
    """Get all books for a user, sorted by most recent first."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                """
                SELECT book_id, user_id, story_id, child_name, pdf_path, thumbnail_path, generation_date, created_at
                FROM books
                WHERE user_id = %s
                ORDER BY generation_date DESC, created_at DESC
                LIMIT %s
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


def delete_book(book_id: int, user_id: int) -> bool:
    """Delete a book. Only allows deletion if book belongs to user."""
    try:
        with get_db_cursor() as cursor:
            # First verify the book belongs to the user
            cursor.execute(
                "SELECT book_id, pdf_path, thumbnail_path FROM books WHERE book_id = %s AND user_id = %s",
                (book_id, user_id)
            )
            row = cursor.fetchone()
            if not row:
                logging.warning(f"[db] Book {book_id} not found or doesn't belong to user {user_id}")
                return False
            
            book_data = dict(row)
            
            # Delete the book record
            cursor.execute(
                "DELETE FROM books WHERE book_id = %s AND user_id = %s",
                (book_id, user_id)
            )
            
            logging.info(f"[db] Book {book_id} deleted for user {user_id}")
            return True
    except Exception as e:
        logging.error(f"[db] Failed to delete book: {e}")
        return False


# -----------------------------------------------------------------------------
# Log operations
# -----------------------------------------------------------------------------

def create_log(user_id: Optional[int], level: str, message: str) -> bool:
    """Create a log entry."""
    try:
        with get_db_cursor() as cursor:
            cursor.execute(
                "INSERT INTO logs (user_id, level, message) VALUES (%s, %s, %s)",
                (user_id, level.upper(), message)
            )
            return True
    except Exception as e:
        # Use standard logging to avoid recursion
        import logging as std_logging
        std_logging.error(f"[db] Failed to create log: {e}")
        return False


def get_logs(user_id: Optional[int] = None, level: Optional[str] = None, limit: int = 100, 
             start_date: Optional[str] = None, end_date: Optional[str] = None,
             search_term: Optional[str] = None) -> List[Dict[str, Any]]:
    """Get logs with optional filters."""
    try:
        with get_db_cursor() as cursor:
            query = "SELECT log_id, user_id, level, message, timestamp FROM logs WHERE 1=1"
            params = []
            
            if user_id is not None:
                query += " AND user_id = %s"
                params.append(user_id)
            
            if level:
                query += " AND level = %s"
                params.append(level.upper())
            
            if start_date:
                query += " AND timestamp >= %s"
                params.append(start_date)
            
            if end_date:
                query += " AND timestamp <= %s"
                params.append(end_date)
            
            if search_term:
                query += " AND message LIKE %s"
                params.append(f"%{search_term}%")
            
            query += " ORDER BY timestamp DESC LIMIT %s"
            params.append(limit)
            
            cursor.execute(query, params)
            rows = cursor.fetchall()
            if rows:
                return [dict(row) for row in rows]
            return []
    except Exception as e:
        import logging as std_logging
        std_logging.error(f"[db] Failed to get logs: {e}")
        return []


def get_log_statistics(start_date: Optional[str] = None, end_date: Optional[str] = None) -> Dict[str, Any]:
    """Get log statistics for reporting."""
    try:
        with get_db_cursor() as cursor:
            where_clause = "WHERE 1=1"
            params = []
            
            if start_date:
                where_clause += " AND timestamp >= %s"
                params.append(start_date)
            
            if end_date:
                where_clause += " AND timestamp <= %s"
                params.append(end_date)
            
            # Get counts by level
            cursor.execute(f"""
                SELECT level, COUNT(*) as count 
                FROM logs 
                {where_clause}
                GROUP BY level
            """, params)
            level_counts = {row['level']: row['count'] for row in cursor.fetchall()}
            
            # Get total count
            cursor.execute(f"SELECT COUNT(*) as total FROM logs {where_clause}", params)
            total = cursor.fetchone()['total']
            
            # Get error frequency (top 10 error messages)
            cursor.execute(f"""
                SELECT message, COUNT(*) as count 
                FROM logs 
                {where_clause} AND level = 'ERROR'
                GROUP BY message 
                ORDER BY count DESC 
                LIMIT 10
            """, params)
            error_frequency = [dict(row) for row in cursor.fetchall()]
            
            # Get success rate (book completed vs started)
            cursor.execute(f"""
                SELECT 
                    SUM(CASE WHEN message LIKE '%%Book generation started%%' THEN 1 ELSE 0 END) as started,
                    SUM(CASE WHEN message LIKE '%%Book completed%%' THEN 1 ELSE 0 END) as completed
                FROM logs 
                {where_clause}
            """, params)
            book_stats = cursor.fetchone()
            started = book_stats['started'] or 0
            completed = book_stats['completed'] or 0
            success_rate = (completed / started * 100) if started > 0 else 0
            
            return {
                "total_logs": total,
                "level_counts": level_counts,
                "error_frequency": error_frequency,
                "book_stats": {
                    "started": started,
                    "completed": completed,
                    "success_rate": round(success_rate, 2)
                }
            }
    except Exception as e:
        import logging as std_logging
        std_logging.error(f"[db] Failed to get log statistics: {e}")
        return {
            "total_logs": 0,
            "level_counts": {},
            "error_frequency": [],
            "book_stats": {"started": 0, "completed": 0, "success_rate": 0}
        }
