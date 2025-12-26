# Fixing Database Connection with Internet Filter

If you have an internet filter/proxy that's blocking database connections, here are solutions:

## Quick Test

Run this to see if it's a network issue:
```bash
python test_network_connectivity.py
```

## Solution 1: Disable Encryption (Temporary)

Internet filters often block encrypted connections. Try disabling encryption:

Add to your `.env` file:
```env
DB_ENCRYPT=no
```

This tells SQL Server to use unencrypted connections, which may bypass your filter.

**⚠️ Warning**: This is less secure, but may be necessary with internet filters.

## Solution 2: Use Local SQL Server Express (Recommended)

If your filter blocks AWS connections, use local SQL Server Express instead:

### Setup Local SQL Server Express:

1. **Install SQL Server Express** (if not already installed)
   - Download: https://www.microsoft.com/en-us/sql-server/sql-server-downloads
   - Choose "Express" edition (free)
   - During installation, choose "Mixed Mode Authentication"
   - Set a password for the `sa` account

2. **Update your `.env` file**:
   ```env
   DB_HOST=localhost
   DB_PORT=1433
   DB_NAME=mystory
   DB_USER=sa
   DB_PASSWORD=your-sql-server-password
   DB_ENCRYPT=no
   ```

3. **Enable SQL Server Browser** (if needed):
   - Open Services (services.msc)
   - Find "SQL Server Browser"
   - Set to "Automatic" and Start it

4. **Enable TCP/IP**:
   - Open SQL Server Configuration Manager
   - SQL Server Network Configuration → Protocols for [INSTANCE]
   - Enable "TCP/IP"
   - Restart SQL Server service

5. **Test connection**:
   ```bash
   python test_sql_connection.py
   ```

## Solution 3: Configure Internet Filter Exception

If you control the filter, add exceptions for:
- AWS RDS endpoints: `*.rds.amazonaws.com`
- Port: 1433 (SQL Server)
- Protocol: TCP

## Solution 4: Use SSH Tunnel (Advanced)

If you have SSH access to a server that can reach AWS:
1. Set up SSH tunnel
2. Connect through the tunnel

## Testing Steps

1. **Test basic connectivity**:
   ```bash
   python test_network_connectivity.py
   ```

2. **If connectivity fails**: It's likely the filter blocking
   - Try local SQL Server Express instead
   - Or configure filter exceptions

3. **If connectivity passes but SQL fails**: 
   - Try `DB_ENCRYPT=no` in `.env`
   - Check AWS security settings
   - Verify credentials

## Current Configuration

Your `.env` should have:
```env
DB_HOST=mystory.c9iogokkc7cl.us-east-2.rds.amazonaws.com
DB_PORT=1433
DB_NAME=mystory
DB_USER=YaacovStuhl
DB_PASSWORD=Mesilos123
DB_ENCRYPT=no  # Add this to bypass filter encryption issues
```

Try adding `DB_ENCRYPT=no` first, then test again!

