# Database Setup Guide

This application uses MySQL for data persistence. The database is compatible with Render MySQL and local development.

## Tables

1. **users** - User accounts (for future OAuth integration)
   - `user_id` (INT AUTO_INCREMENT PRIMARY KEY)
   - `email` (VARCHAR, UNIQUE)
   - `oauth_provider` (VARCHAR)
   - `created_at` (TIMESTAMP)

2. **storylines** - Vetted story configurations
   - `story_id` (VARCHAR PRIMARY KEY) - e.g., "lrrh", "jatb"
   - `name` (VARCHAR) - Display name
   - `gender` (VARCHAR) - "girl" or "boy"
   - `pages` (INT) - Number of pages (default 12)
   - `pages_json` (JSON) - Full story configuration

3. **books** - Generated storybooks
   - `book_id` (INT AUTO_INCREMENT PRIMARY KEY)
   - `user_id` (INT, FK to users)
   - `story_id` (VARCHAR, FK to storylines)
   - `child_name` (VARCHAR)
   - `pdf_path` (VARCHAR) - Relative path to PDF file
   - `created_at` (TIMESTAMP)

4. **logs** - Application logs
   - `log_id` (INT AUTO_INCREMENT PRIMARY KEY)
   - `user_id` (INT, FK to users, nullable)
   - `level` (VARCHAR) - DEBUG, INFO, WARNING, ERROR, CRITICAL
   - `message` (TEXT)
   - `timestamp` (TIMESTAMP)

## Setup Instructions

### For Render Deployment

1. **Create MySQL Database on Render**
   - Go to your Render dashboard
   - Create a new MySQL database
   - Render automatically provides `DATABASE_URL` environment variable

2. **Initialize Database Schema**
   - The schema will be automatically initialized on first app startup
   - Or run manually: `python init_db.py`

3. **Load Storylines**
   - Storylines are automatically loaded from config files on first startup
   - Or run: `python init_db.py` to manually load

### For Local Development

1. **Install MySQL**
   - Install MySQL on your system (or use XAMPP which includes MySQL)
   - Start MySQL service

2. **Create Database**
   ```sql
   CREATE DATABASE mystory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```

3. **Set Environment Variables**
   Add to your `.env` file:
   ```env
   # Option 1: Full connection string
   DATABASE_URL=mysql://root:your_password@localhost:3306/mystory
   
   # Option 2: Individual components
   DB_HOST=localhost
   DB_PORT=3306
   DB_NAME=mystory
   DB_USER=root
   DB_PASSWORD=your_password
   ```

4. **Initialize Database**
   ```bash
   python init_db.py
   ```
   This will:
   - Create all tables
   - Load storylines from config files into database

5. **Verify Setup**
   ```bash
   mysql -u root -p mystory -e "SELECT story_id, name FROM storylines;"
   ```

## Database Connection

The application uses a connection pool for efficient database access:
- Pool size: 10 connections
- Automatic connection management
- UTF-8 encoding (utf8mb4) for full Unicode support

## Fallback Behavior

If the database is not available:
- Storylines load from config files (fallback)
- Books are still generated (just not saved to database)
- Logs are written to console only
- Application continues to function normally

## Migration from Config Files

Storylines are automatically migrated from config files to database:
- On first startup, if database is available
- Config files remain as fallback
- Database is preferred source when available

## API Usage

### Creating a Book (with user_id)
```python
# In your route handler
user_id = get_current_user_id()  # From session/OAuth
book = database.create_book(user_id, "lrrh", "Alice", "storybook_abc123.pdf")
```

### Getting User's Books
```python
books = database.get_user_books(user_id, limit=50)
```

### Logging
```python
database.create_log(user_id, "INFO", "Book generation started")
database.create_log(user_id, "ERROR", "Failed to generate image")
```

## Troubleshooting

### Connection Errors
- Check `DATABASE_URL` is set correctly
- Verify MySQL is running: `mysqladmin ping` or check services
- Check firewall/network settings
- Verify database exists: `mysql -u root -p -e "SHOW DATABASES;"`

### Schema Errors
- Run `python init_db.py` to recreate schema
- Check `schema.sql` for table definitions
- MySQL version 5.7+ required for JSON support

### Storyline Not Found
- Verify storylines are loaded: `SELECT * FROM storylines;`
- Run `python init_db.py` to reload from config files
- Application will fallback to config files automatically

### XAMPP Users
If using XAMPP:
- MySQL is usually on port 3306
- Default user: `root`
- Default password: (empty) or check your XAMPP configuration
- Access phpMyAdmin at: http://localhost/phpmyadmin
