# SQL Server Express Setup Guide

Your application is now configured to use SQL Server Express (or AWS RDS SQL Server).

## Quick Setup Steps

### 1. Install ODBC Driver (if not already installed)

**For Windows:**
1. Download Microsoft ODBC Driver for SQL Server:
   - Go to: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server
   - Download "ODBC Driver 17 for SQL Server" or "ODBC Driver 18 for SQL Server"
   - Install it

**Check if already installed:**
```powershell
Get-OdbcDriver | Where-Object {$_.Name -like "*SQL Server*"}
```

### 2. Update Your .env File

Your `.env` file should have:
```env
DB_HOST=mystory.c9iogokkc7cl.us-east-2.rds.amazonaws.com
DB_PORT=1433
DB_NAME=mystory
DB_USER=YaacovStuhl
DB_PASSWORD=Mesilos123
```

✅ **Your port is already correct (1433) for SQL Server!**

### 3. Make Database Publicly Accessible

**In AWS RDS Console:**
1. Click your database instance
2. Click **"Modify"**
3. Under "Connectivity", change **"Public access"** to **"Yes"**
4. Choose **"Apply immediately"**
5. Click **"Modify DB instance"**
6. Wait 5-10 minutes

### 4. Update Security Group

**In EC2 Console:**
1. Search for "EC2" in AWS Console
2. Click "Security Groups" in left sidebar
3. Find your security group (from RDS page)
4. Click "Edit inbound rules"
5. Add rule:
   - **Type**: MS SQL
   - **Port**: **1433**
   - **Source**: My IP
6. Save rules

### 5. Create Database (if needed)

```bash
python create_aws_database.py
```

### 6. Initialize Schema

```bash
python init_db.py
```

### 7. Run OAuth Migration

```bash
python migrate_oauth_schema.py
```

## Testing Connection

Test your connection:
```bash
python -c "import database; database.init_connection_pool(); print('✓ Connected to SQL Server!')"
```

## Troubleshooting

### "Driver not found" error
- Install ODBC Driver 17 or 18 for SQL Server
- Download from: https://learn.microsoft.com/en-us/sql/connect/odbc/download-odbc-driver-for-sql-server

### "Can't connect" error
- Check "Publicly accessible" is "Yes" in RDS
- Verify security group allows port 1433 from your IP
- Check database status is "Available"

### "Login failed" error
- Verify username and password in .env
- Check SQL Server authentication is enabled (not just Windows auth)

## Your Current Configuration

Based on your AWS page:
- ✅ Endpoint: `mystory.c9iogokkc7cl.us-east-2.rds.amazonaws.com`
- ✅ Port: `1433` (correct for SQL Server!)
- ⚠️ Public access: Needs to be "Yes"
- ⚠️ Security group: Needs to allow port 1433

Once you make those two changes in AWS, everything should work!

