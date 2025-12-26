# XAMPP MySQL Setup Guide

This guide will help you configure the application to work with XAMPP's MySQL database.

## Step 1: Start XAMPP MySQL

1. Open **XAMPP Control Panel**
2. Make sure **MySQL** is running (click "Start" if it's not)
3. The MySQL service should show "Running" status

## Step 2: Create Database

You can create the database using either method:

### Option A: Using phpMyAdmin (Easier)

1. In XAMPP Control Panel, click **"Admin"** next to MySQL (or go to http://localhost/phpmyadmin)
2. Click **"New"** in the left sidebar
3. Database name: `mystory`
4. Collation: `utf8mb4_unicode_ci`
5. Click **"Create"**

### Option B: Using MySQL Command Line

1. Open Command Prompt
2. Navigate to XAMPP MySQL bin directory:
   ```cmd
   cd C:\xampp\mysql\bin
   ```
3. Connect to MySQL:
   ```cmd
   mysql.exe -u root
   ```
   (If you set a password, use: `mysql.exe -u root -p`)
4. Create database:
   ```sql
   CREATE DATABASE mystory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
   ```
5. Exit:
   ```sql
   exit;
   ```

## Step 3: Configure .env File

Copy `env.sample` to `.env` (if you haven't already) and configure:

```env
# Database Configuration (XAMPP MySQL)
DB_HOST=localhost
DB_PORT=3306
DB_NAME=mystory
DB_USER=root
DB_PASSWORD=
```

**Important Notes:**
- If your XAMPP MySQL root user has NO password (default), leave `DB_PASSWORD=` empty
- If you set a password for MySQL root user, add it: `DB_PASSWORD=your_password`
- Do NOT use `DATABASE_URL` - use the individual components above

## Step 4: Initialize Database

Run the initialization script:

```bash
python init_db.py
```

This will:
- Create all required tables
- Load storylines from config files
- Set up indexes

## Step 5: Verify Connection

Test the connection:

```bash
python check_env.py
```

You should see:
```
✓ Configuration looks good!
```

## Troubleshooting

### "Can't connect to MySQL server"
- Make sure MySQL is running in XAMPP Control Panel
- Check that port 3306 is not blocked by firewall
- Verify XAMPP MySQL is actually running (green status)

### "Access denied for user 'root'@'localhost'"
- If you set a MySQL password, make sure `DB_PASSWORD` in `.env` matches
- If MySQL has no password, make sure `DB_PASSWORD=` is empty (not commented out)

### "Unknown database 'mystory'"
- Create the database first (see Step 2)
- Make sure the database name in `.env` matches exactly: `mystory`

### "Table already exists" errors
- This is normal if you've run `init_db.py` before
- The script will skip existing tables safely

## Default XAMPP MySQL Settings

- **Host:** localhost
- **Port:** 3306
- **User:** root
- **Password:** (usually empty/blank by default)
- **Socket:** (not needed for TCP/IP connection)

## Next Steps

After setup is complete:
1. Start your Flask app: `flask run`
2. Visit http://localhost:5000
3. Register a new account or login
4. Create your first storybook!

