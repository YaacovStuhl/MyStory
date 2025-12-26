# Fixing AWS RDS Connection Issues

## Issue 1: Port is Wrong (1433 vs 3306)

**Problem**: Port 1433 is for SQL Server, not MySQL. MySQL uses port 3306.

**Check**: In AWS RDS console, look at your database:
- If it says "Engine: MySQL" → Should use port 3306
- If it says "Engine: SQL Server" → You created the wrong database type!

**Solution**:
1. If you created SQL Server by mistake, you need to create a new MySQL database
2. Update your `.env` file to use port 3306

## Issue 2: Publicly Accessible is "No"

**Problem**: Your database is set to "Publicly accessible: No", which means it can only be accessed from within AWS VPC, not from your computer.

**Solution**: Make it publicly accessible:

1. In AWS RDS console, click on your database instance
2. Click "Modify" button (top right)
3. Scroll down to "Connectivity"
4. Under "Public access", change it to **"Publicly accessible: Yes"**
5. Scroll to bottom, click "Continue"
6. Choose "Apply immediately" (or schedule for next maintenance window)
7. Click "Modify DB instance"
8. Wait 5-10 minutes for the change to apply

## Issue 3: Security Group Rules

**Problem**: The default security group might not allow MySQL connections from your IP.

**Solution**: Update security group:

1. In RDS console, click your database
2. Under "Connectivity & security", find "VPC security groups"
3. Click on the security group (e.g., `default (sg-03cf575787ba9f03e)`)
4. Click "Edit inbound rules"
5. Click "Add rule"
6. Configure:
   - **Type**: MySQL/Aurora
   - **Protocol**: TCP
   - **Port range**: 3306 (NOT 1433!)
   - **Source**: 
     - Click "My IP" (automatically adds your IP)
     - OR manually enter your IP address
   - **Description**: "Allow MySQL from my computer"
7. Click "Save rules"

## Issue 4: Verify Database Type

**Check what you created**:
1. In RDS console, click your database
2. Look at "Engine" - it should say "MySQL" not "SQL Server"
3. If it says SQL Server, you need to create a new MySQL database

## Quick Fix Checklist

- [ ] Database engine is MySQL (not SQL Server)
- [ ] Publicly accessible is set to "Yes"
- [ ] Security group allows port 3306 (not 1433) from your IP
- [ ] `.env` file has correct port (3306)
- [ ] Database status is "Available"

## After Fixing

1. Update your `.env` file:
   ```env
   DB_HOST=mystory.c9iogokkc7cl.us-east-2.rds.amazonaws.com
   DB_PORT=3306
   DB_NAME=mystory
   DB_USER=admin
   DB_PASSWORD=your-password
   ```

2. Test connection:
   ```bash
   python create_aws_database.py
   ```

