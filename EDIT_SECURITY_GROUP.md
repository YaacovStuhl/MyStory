# How to Edit Security Group Rules

Security groups are managed in the **EC2 console**, not the RDS console. Here's how to edit them:

## Method 1: From EC2 Console (Recommended)

### Step 1: Go to EC2 Console
1. In AWS Console, search for **"EC2"** in the search bar
2. Click on **"EC2"** service

### Step 2: Find Your Security Group
1. In the left sidebar, click **"Security Groups"**
2. You'll see a list of security groups
3. Find the one your RDS database is using:
   - Look for: `default (sg-03cf575787ba9f03e)` or similar
   - Or search by the security group ID from your RDS page

### Step 3: Edit Inbound Rules
1. **Select** the security group (click the checkbox)
2. Click the **"Inbound rules"** tab at the bottom
3. Click **"Edit inbound rules"** button
4. Click **"Add rule"**
5. Configure:
   - **Type**: MySQL/Aurora (or "Custom TCP")
   - **Protocol**: TCP
   - **Port range**: **3306**
   - **Source**: 
     - Click dropdown, select **"My IP"** (automatically adds your IP)
     - OR select "Custom" and enter your IP manually
   - **Description**: "Allow MySQL from my computer"
6. Click **"Save rules"**

## Method 2: From RDS Console (Alternative)

If you can't access EC2, try this:

1. In **RDS console**, click your database
2. Under "Connectivity & security", find **"VPC security groups"**
3. Click the **security group ID** (the blue link, e.g., `sg-03cf575787ba9f03e`)
4. This should open EC2 console with that security group selected
5. Then follow Step 3 above

## Method 3: Create New Security Group (If Still Can't Edit)

If the default security group is restricted, create a new one:

### Create New Security Group:
1. Go to **EC2 Console** → **Security Groups**
2. Click **"Create security group"**
3. Configure:
   - **Name**: `mystory-db-access`
   - **Description**: "Security group for MyStory database access"
   - **VPC**: Select the same VPC as your RDS (from RDS page: `vpc-05c101957d8297545`)
4. **Add inbound rule**:
   - Type: MySQL/Aurora
   - Port: 3306
   - Source: My IP
5. Click **"Create security group"**

### Attach to RDS:
1. Go back to **RDS Console**
2. Click your database instance
3. Click **"Modify"**
4. Scroll to **"Connectivity"**
5. Under **"VPC security groups"**, click the dropdown
6. **Add** your new security group (`mystory-db-access`)
7. **Remove** the old one if needed
8. Click **"Continue"** → **"Apply immediately"** → **"Modify DB instance"**

## Troubleshooting

### "You don't have permission"
- Make sure you're logged in as the root account or an account with EC2 permissions
- Check IAM permissions if using a different user

### "Can't find security group"
- Copy the security group ID from RDS page (e.g., `sg-03cf575787ba9f03e`)
- Paste it in EC2 Security Groups search box

### Still grayed out?
- Try creating a new security group (Method 3)
- Or check if you're using AWS Free Tier with restrictions

