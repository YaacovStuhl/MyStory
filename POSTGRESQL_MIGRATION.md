# PostgreSQL Migration Guide

## Overview

The application now supports **both MySQL and PostgreSQL** with automatic detection. This allows you to use Render's built-in PostgreSQL database instead of requiring an external MySQL service.

## How It Works

The app automatically detects the database type from the `DATABASE_URL`:
- `postgresql://` or `postgres://` → PostgreSQL
- `mysql://` → MySQL

If no `DATABASE_URL` is provided, it uses:
- Port `5432` → PostgreSQL
- Port `3306` → MySQL

## Key Differences Handled

### 1. Connection Libraries
- **PostgreSQL**: Uses `psycopg2-binary` (already in requirements.txt)
- **MySQL**: Uses `PyMySQL` (already in requirements.txt)

### 2. SQL Syntax Differences

| Feature | MySQL | PostgreSQL |
|---------|-------|------------|
| Auto-increment | `AUTO_INCREMENT` | `SERIAL` |
| Upsert | `ON DUPLICATE KEY UPDATE` | `ON CONFLICT ... DO UPDATE` |
| Get inserted ID | `cursor.lastrowid` | `RETURNING id` |
| Values reference | `VALUES(column)` | `EXCLUDED.column` |

All these differences are handled automatically in `database.py`.

### 3. Schema Files

- **MySQL**: `schema.sql` (original)
- **PostgreSQL**: `schema_postgresql.sql` (new)

The `init_database()` function automatically selects the correct schema file based on the detected database type.

## Using PostgreSQL on Render

### Step 1: Create PostgreSQL Database

1. In Render dashboard: **New +** → **PostgreSQL**
2. Configure:
   - Name: `mystory-db`
   - Database: `mystory`
   - Plan: Free (for testing)
3. Click **Create Database**

### Step 2: Link to Web Service

In your `render.yaml`:
```yaml
envVars:
  - key: DATABASE_URL
    fromDatabase:
      name: mystory-db
      property: connectionString
```

Or manually set in Render dashboard:
- Go to your web service
- Environment tab
- Add `DATABASE_URL` (automatically populated if database is linked)

### Step 3: Initialize Database

After deployment, run in Render Shell:
```bash
python init_db.py
```

This will:
- Detect PostgreSQL from `DATABASE_URL`
- Load `schema_postgresql.sql`
- Create all tables and indexes

## Testing Locally with PostgreSQL

### Option 1: Use Local PostgreSQL

1. Install PostgreSQL locally
2. Create database:
   ```sql
   CREATE DATABASE mystory;
   ```
3. Set in `.env`:
   ```env
   DATABASE_URL=postgresql://postgres:password@localhost:5432/mystory
   ```
4. Run `python init_db.py`

### Option 2: Use Render PostgreSQL Locally

1. Get connection string from Render dashboard
2. Add to `.env`:
   ```env
   DATABASE_URL=postgresql://user:pass@host.onrender.com:5432/mystory
   ```
3. Run `python init_db.py`

## Migration from MySQL to PostgreSQL

If you have existing data in MySQL:

1. **Export data** from MySQL:
   ```bash
   mysqldump -u user -p mystory > backup.sql
   ```

2. **Create PostgreSQL database** on Render

3. **Import data** (requires manual conversion):
   - Convert SQL syntax (AUTO_INCREMENT → SERIAL, etc.)
   - Import to PostgreSQL
   - Or use a migration tool

4. **Update DATABASE_URL** to PostgreSQL connection string

5. **Test thoroughly** before switching production

## Verification

To check which database type is being used:

```python
from database import get_db_type
print(f"Database type: {get_db_type()}")
```

Or check logs:
```
[db] Database schema initialized successfully (postgresql)
```

## Troubleshooting

### "psycopg2-binary is required"

Install it:
```bash
pip install psycopg2-binary
```

### "schema_postgresql.sql not found"

Make sure the file exists in your project root. It's included in the repository.

### Connection Errors

- Verify `DATABASE_URL` starts with `postgresql://`
- Check database credentials
- Ensure database is accessible (for external databases)

### SQL Syntax Errors

If you see PostgreSQL-specific errors, check:
- All SQL queries use parameterized queries (`%s` placeholders)
- No MySQL-specific functions are used
- Schema file matches your database type

## Benefits of PostgreSQL on Render

✅ **Native support** - No external service needed  
✅ **Automatic backups** - Built into Render  
✅ **Easy scaling** - Upgrade plan as needed  
✅ **Integrated** - Works seamlessly with Render services  
✅ **Free tier available** - For testing and development  

## Next Steps

1. Create PostgreSQL database on Render
2. Deploy your app
3. Initialize database with `init_db.py`
4. Test your application
5. Monitor logs for any database-related issues

