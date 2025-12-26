"""
Test network connectivity to AWS RDS SQL Server.
Helps diagnose if internet filter is blocking the connection.
"""

import socket
import os
from dotenv import load_dotenv

load_dotenv()


def test_connectivity():
    """Test basic network connectivity to the database server."""
    host = os.getenv("DB_HOST", "mystory.c9iogokkc7cl.us-east-2.rds.amazonaws.com")
    port = int(os.getenv("DB_PORT", "1433"))
    
    print("=" * 60)
    print("Network Connectivity Test")
    print("=" * 60)
    print(f"Testing connection to: {host}:{port}")
    print()
    
    # Test 1: DNS Resolution
    print("Test 1: DNS Resolution...")
    try:
        ip = socket.gethostbyname(host)
        print(f"OK DNS resolved: {host} -> {ip}")
    except Exception as e:
        print(f"X DNS failed: {e}")
        print("  This suggests a network/DNS issue")
        return False
    
    # Test 2: TCP Connection
    print("\nTest 2: TCP Connection (port {})...".format(port))
    try:
        sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        sock.settimeout(10)
        result = sock.connect_ex((host, port))
        sock.close()
        
        if result == 0:
            print(f"OK TCP connection successful on port {port}")
        else:
            print(f"X TCP connection failed (error code: {result})")
            print("  This suggests:")
            print("  - Security group is blocking the connection")
            print("  - Internet filter/proxy is blocking the connection")
            print("  - Firewall is blocking the connection")
            return False
    except Exception as e:
        print(f"X TCP connection error: {e}")
        print("  This could be an internet filter blocking the connection")
        return False
    
    # Test 3: Try different ports (to see if filter is port-specific)
    print("\nTest 3: Testing other common ports...")
    test_ports = [1433, 3306, 5432, 80, 443]
    for test_port in test_ports:
        if test_port == port:
            continue
        try:
            sock = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            sock.settimeout(5)
            result = sock.connect_ex((host, test_port))
            sock.close()
            if result == 0:
                print(f"  Port {test_port}: Open (unexpected)")
        except:
            pass
    
    print("\nOK Basic network connectivity test passed!")
    print("  If this passes but SQL connection fails, it's likely:")
    print("  - SSL/TLS handshake issue (internet filter)")
    print("  - SQL Server authentication issue")
    print("  - Database not publicly accessible")
    return True


if __name__ == "__main__":
    if test_connectivity():
        print("\nNetwork is reachable. SQL connection issues are likely:")
        print("1. SSL/TLS problems (internet filter)")
        print("2. Database authentication")
        print("3. Database not publicly accessible")
    else:
        print("\nNetwork connectivity failed. This suggests:")
        print("1. Internet filter/proxy is blocking the connection")
        print("2. Security group is blocking the connection")
        print("3. Firewall is blocking the connection")

