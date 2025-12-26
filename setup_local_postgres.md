# Local PostgreSQL Setup Guide

You've installed PostgreSQL locally. Here's how to configure it for this project.

## Step 1: Verify PostgreSQL is Running

**Windows:**
```powershell
# Check if PostgreSQL service is running
Get-Service -Name postgresql*
```

If it's not running, start it:
```powershell
Start-Service postgresql-x64-15  # (version number may vary)
```

Or start it from Services:
1. Press `Win + R`, type `services.msc`
2. Find "postgresql" service
3. Right-click → Start

## Step 2: Set PostgreSQL Password (if needed)

If you haven't set a password for the `postgres` user:

1. Open Command Prompt or PowerShell
2. Navigate to PostgreSQL bin directory (usually):
   ```powershell
   cd "C:\Program Files\PostgreSQL\15\bin"
   ```
   (Replace `15` with your PostgreSQL version)

3. Connect to PostgreSQL:
   ```powershell
   psql -U postgres
   ```

4. Set password:
   ```sql
   ALTER USER postgres PASSWORD 'your_password_here';
   \q
   ```

## Step 3: Create Database

Create the database for this project:

```powershell
# Using psql command line
psql -U postgres -c "CREATE DATABASE mystory;"
```

Or using psql interactively:
```powershell
psql -U postgres
```
Then in psql:
```sql
CREATE DATABASE mystory;
\q
```

## Step 4: Update Your .env File

Your `.env` file should have:

```env
# Local PostgreSQL Configuration
DB_HOST=localhost
DB_PORT=5432
DB_NAME=mystory
DB_USER=postgres
DB_PASSWORD=your_postgres_password_here
```

**Important:** Replace `your_postgres_password_here` with the actual password you set for the `postgres` user.

## Step 5: Test Connection

```bash
python check_env.py
```

## Step 6: Initialize Database

```bash
python init_db.py
```

## Troubleshooting

### "Password authentication failed"
- Make sure you're using the correct password for the `postgres` user
- If you forgot the password, you can reset it (see Step 2)

### "Database does not exist"
- Create the database: `psql -U postgres -c "CREATE DATABASE mystory;"`

### "Connection refused" or "Could not connect"
- Make sure PostgreSQL service is running (see Step 1)
- Check that port 5432 is not blocked by firewall

### "psql: command not found"
- Add PostgreSQL bin directory to your PATH, or use full path:
  ```powershell
  "C:\Program Files\PostgreSQL\15\bin\psql.exe" -U postgres
  ```


