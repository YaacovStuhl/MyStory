# AWS RDS PostgreSQL Setup Guide

Your application now uses PostgreSQL. If you have an AWS RDS SQL Server or MySQL instance, you need to create a PostgreSQL RDS instance instead.

## Step 1: Create AWS RDS PostgreSQL Instance

### 1.1 Log into AWS Console
1. Go to https://aws.amazon.com/console/
2. Sign in with your AWS account
3. Make sure you're in the correct region (e.g., `us-east-2`)

### 1.2 Create RDS Database
1. In AWS Console, search for "RDS" in the search bar
2. Click "RDS" service
3. Click "Create database" button

### 1.3 Configure Database Settings

**Database creation method:**
- Choose "Standard create"

**Engine options:**
- Engine type: **PostgreSQL** (NOT MySQL or SQL Server!)
- Version: **PostgreSQL 15.x** or latest available

**Templates:**
- For development/testing: Choose **"Free tier"** (if eligible)
- For production: Choose **"Production"** or **"Dev/Test"**

**Settings:**
- **DB instance identifier**: `mystory-postgres` (or any name you like)
- **Master username**: `postgres` (or your preferred username)
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
- **Public access**: **YES** (required to connect from your computer)
- **VPC security group**: Create new
  - Security group name: `mystory-postgres-sg`
- **Availability Zone**: No preference
- **Database port**: **5432** (PostgreSQL default port - IMPORTANT!)

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
1. In RDS console, click on your PostgreSQL database instance
2. Under "Connectivity & security", find "VPC security groups"
3. Click on the security group (e.g., `mystory-postgres-sg`)

### 2.2 Add Inbound Rule
1. Click "Edit inbound rules"
2. Click "Add rule"
3. Configure:
   - **Type**: PostgreSQL
   - **Protocol**: TCP
   - **Port**: **5432** (PostgreSQL port)
   - **Source**: 
     - For testing: `My IP` (your current IP address)
     - For production: Specific IP or CIDR block
     - ⚠️ **NOT** `0.0.0.0/0` (allows anyone - security risk!)
4. Click "Save rules"

## Step 3: Get Connection Information

### 3.1 Find Endpoint
1. In RDS console, click on your PostgreSQL database instance
2. Under "Connectivity & security", find "Endpoint"
3. Copy the endpoint (looks like: `mystory-postgres.abc123.us-east-2.rds.amazonaws.com`)
4. Note the port (should be 5432)

### 3.2 Connection Details
You'll need:
- **Host/Endpoint**: `mystory-postgres.abc123.us-east-2.rds.amazonaws.com`
- **Port**: `5432`
- **Database name**: `mystory` (or the name you created)
- **Username**: The master username you set (e.g., `postgres`)
- **Password**: The master password you created

## Step 4: Update Your .env File

Update your `.env` file with the PostgreSQL connection details:

```env
# AWS RDS PostgreSQL Configuration
DB_HOST=mystory-postgres.abc123.us-east-2.rds.amazonaws.com
DB_PORT=5432
DB_NAME=mystory
DB_USER=postgres
DB_PASSWORD=your-strong-password-here
```

**Or use connection string format:**
```env
DATABASE_URL=postgresql://postgres:your-password@mystory-postgres.abc123.us-east-2.rds.amazonaws.com:5432/mystory
```

## Step 5: Test Connection

Run the check script to verify your configuration:
```bash
python check_env.py
```

## Step 6: Initialize Database

Once your .env is configured correctly:
```bash
python init_db.py
```

This will:
- Create all tables
- Load storylines from config files into database

## Troubleshooting

### "Connection timeout" or "Can't connect"
- Make sure "Public access" is set to "Yes" in RDS console
- Check security group allows port 5432 from your IP
- Verify the endpoint is correct

### "Authentication failed"
- Double-check your username and password
- Make sure you're using the master username/password you set during creation

### "Database does not exist"
- The database will be created automatically when you run `init_db.py`
- Or create it manually in AWS RDS console

### Port 1433 vs 5432
- **1433** = SQL Server (wrong for this app)
- **3306** = MySQL (wrong for this app)
- **5432** = PostgreSQL (correct!)

## Cost Considerations

- **Free tier**: If eligible, you get 750 hours/month of db.t2.micro or db.t3.micro
- **Paid**: db.t3.micro costs ~$15/month, db.t3.small ~$30/month
- **Storage**: First 20GB of gp3 storage is included, then ~$0.115/GB/month

## Next Steps

After setting up PostgreSQL RDS:
1. Update your `.env` file with the new connection details
2. Run `python check_env.py` to verify
3. Run `python init_db.py` to initialize the database
4. Start your application: `flask run`


