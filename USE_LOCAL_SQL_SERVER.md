# Using Local SQL Server Express Instead

Since your internet filter is blocking AWS connections, let's use **local SQL Server Express** instead. This will work completely offline and bypass the filter.

## Quick Setup

### Option 1: If SQL Server Express is Already Installed

1. **Check if it's running**:
   - Open Services (press Win+R, type `services.msc`)
   - Look for "SQL Server (MSSQLSERVER)" or "SQL Server (SQLEXPRESS)"
   - If it's not running, right-click → Start

2. **Update your `.env` file**:
   ```env
   DB_HOST=localhost
   DB_PORT=1433
   DB_NAME=mystory
   DB_USER=sa
   DB_PASSWORD=your-sql-server-password
   DB_ENCRYPT=no
   ```

3. **Test connection**:
   ```bash
   python test_sql_connection.py
   ```

### Option 2: Install SQL Server Express (Free)

1. **Download SQL Server Express**:
   - Go to: https://www.microsoft.com/en-us/sql-server/sql-server-downloads
   - Click "Download now" under "Express" (free edition)
   - Run the installer

2. **During Installation**:
   - Choose "Basic" installation (easiest)
   - **IMPORTANT**: Choose "Mixed Mode Authentication"
   - Set a password for the `sa` account (save this!)
   - Complete the installation

3. **Enable TCP/IP** (if needed):
   - Open "SQL Server Configuration Manager"
   - SQL Server Network Configuration → Protocols for [INSTANCE]
   - Right-click "TCP/IP" → Enable
   - Restart SQL Server service

4. **Update `.env`**:
   ```env
   DB_HOST=localhost
   DB_PORT=1433
   DB_NAME=mystory
   DB_USER=sa
   DB_PASSWORD=the-password-you-set
   DB_ENCRYPT=no
   ```

5. **Test and setup**:
   ```bash
   python test_sql_connection.py
   python create_aws_database.py  # (will create local database)
   python init_db.py
   python migrate_oauth_schema.py
   ```

## Benefits of Local SQL Server

- ✅ No internet filter issues
- ✅ Faster (local connection)
- ✅ Free (SQL Server Express)
- ✅ Works offline
- ✅ No AWS costs
- ✅ Full control

## Finding Your SQL Server Instance Name

If you're not sure of the instance name:
- Check Services for "SQL Server (INSTANCENAME)"
- Or try: `localhost\SQLEXPRESS` or `localhost\MSSQLSERVER`

If you need help finding your SQL Server setup, let me know!

