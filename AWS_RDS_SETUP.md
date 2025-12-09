# AWS RDS MySQL Setup Guide

This guide will help you set up AWS RDS (Relational Database Service) for MySQL and connect your application to it.

## Step 1: Create AWS RDS MySQL Instance

### 1.1 Log into AWS Console
1. Go to https://aws.amazon.com/console/
2. Sign in with your AWS account
3. Make sure you're in the correct region (e.g., `us-east-1`)

### 1.2 Create RDS Database
1. In AWS Console, search for "RDS" in the search bar
2. Click "RDS" service
3. Click "Create database" button

### 1.3 Configure Database Settings

**Database creation method:**
- Choose "Standard create"

**Engine options:**
- Engine type: **MySQL**
- Version: **MySQL 8.0** (or latest available)

**Templates:**
- For development/testing: Choose **"Free tier"** (if eligible)
- For production: Choose **"Production"** or **"Dev/Test"**

**Settings:**
- **DB instance identifier**: `mystory-db` (or any name you like)
- **Master username**: `admin` (or your preferred username)
- **Master password**: Create a strong password (save this!)
  - Must be 8-40 characters
  - Include uppercase, lowercase, numbers, and special characters

**Instance configuration:**
- **DB instance class**: 
  - Free tier: `db.t3.micro` or `db.t2.micro`
  - Paid: `db.t3.small` or larger

**Storage:**
- **Storage type**: General Purpose SSD (gp3)
- **Allocated storage**: 20 GB (minimum, adjust as needed)
- **Storage autoscaling**: Enable if you want automatic scaling

**Connectivity:**
- **Virtual Private Cloud (VPC)**: Use default VPC (or create one)
- **Subnet group**: default
- **Public access**: **YES** (for now, so you can connect from your computer)
- **VPC security group**: Create new
  - Security group name: `mystory-db-sg`
- **Availability Zone**: No preference
- **Database port**: `3306` (default MySQL port)

**Database authentication:**
- **Password authentication** (default)

**Additional configuration:**
- **Initial database name**: `mystory` (optional, you can create it later)
- **Backup retention**: 7 days (or as needed)
- **Enable encryption**: Optional (recommended for production)

### 1.4 Create Database
- Click "Create database"
- Wait 5-10 minutes for the database to be created
- You'll see "Creating" status, then "Available"

## Step 2: Configure Security Group

### 2.1 Update Security Group Rules
1. In RDS console, click on your database instance
2. Under "Connectivity & security", find "VPC security groups"
3. Click on the security group (e.g., `mystory-db-sg`)

### 2.2 Add Inbound Rule
1. Click "Edit inbound rules"
2. Click "Add rule"
3. Configure:
   - **Type**: MySQL/Aurora
   - **Protocol**: TCP
   - **Port**: 3306
   - **Source**: 
     - For testing: `My IP` (your current IP address)
     - For production: Specific IP or CIDR block
     - ⚠️ **NOT** `0.0.0.0/0` (allows anyone - security risk!)
4. Click "Save rules"

## Step 3: Get Connection Information

### 3.1 Find Endpoint
1. In RDS console, click on your database instance
2. Under "Connectivity & security", find "Endpoint"
3. Copy the endpoint (looks like: `mystory-db.abc123.us-east-1.rds.amazonaws.com`)
4. Note the port (usually 3306)

### 3.2 Connection Details
You'll need:
- **Host/Endpoint**: `mystory-db.abc123.us-east-1.rds.amazonaws.com`
- **Port**: `3306`
- **Database name**: `mystory` (or the name you created)
- **Username**: The master username you set (e.g., `admin`)
- **Password**: The master password you created

## Step 4: Update Your .env File

Add these to your `.env` file:

```env
# AWS RDS MySQL Configuration
DB_HOST=mystory-db.abc123.us-east-1.rds.amazonaws.com
DB_PORT=3306
DB_NAME=mystory
DB_USER=admin
DB_PASSWORD=your-strong-password-here
```

**Or use connection string format:**
```env
DATABASE_URL=mysql://admin:your-password@mystory-db.abc123.us-east-1.rds.amazonaws.com:3306/mystory
```

## Step 5: Create Database (if not created)

If you didn't create the database during setup, connect and create it:

### Option A: Using MySQL Command Line (if installed)
```bash
mysql -h your-endpoint.rds.amazonaws.com -P 3306 -u admin -p
# Enter password when prompted
CREATE DATABASE mystory CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
EXIT;
```

### Option B: Using Python Script
I'll create a script to do this for you.

## Step 6: Initialize Database Schema

Run the initialization script:
```bash
python init_db.py
```

This will:
- Create all tables (users, storylines, books, logs)
- Load storylines from config files

## Step 7: Test Connection

Test your connection:
```bash
python -c "import database; database.init_connection_pool(); print('✓ Connected to AWS RDS!')"
```

## Cost Considerations

### Free Tier (if eligible)
- 750 hours/month of db.t2.micro or db.t3.micro
- 20 GB storage
- 20 GB backup storage
- Valid for 12 months for new AWS accounts

### After Free Tier
- db.t3.micro: ~$15/month
- Storage: ~$0.115/GB/month
- Data transfer: First 100 GB/month free, then ~$0.09/GB

**Tip**: Stop the database when not in use to save costs (you can start/stop it anytime).

## Security Best Practices

1. **Use strong passwords** (12+ characters, mixed case, numbers, symbols)
2. **Limit security group access** to your IP only
3. **Enable encryption** for production databases
4. **Regular backups** (automatically configured)
5. **Don't commit passwords** to git (use .env file, add to .gitignore)

## Troubleshooting

### "Can't connect to MySQL server"
- Check security group allows your IP
- Verify endpoint and port are correct
- Check database status is "Available"
- Verify username and password

### "Access denied"
- Check username and password
- Verify database name exists
- Check user has proper permissions

### "Connection timeout"
- Security group might not allow your IP
- Database might be in a private subnet
- Check VPC and subnet configuration

## Next Steps

Once connected:
1. Run `python migrate_oauth_schema.py` (if needed)
2. Run `python init_db.py` to create tables
3. Start your Flask app: `flask run`
4. Test OAuth login


