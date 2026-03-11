"""Real-time connectivity check for Plex clients."""

import socket
import asyncio


async def check_client_connectivity(client_ip: str, timeout: float = 2.0) -> bool:
    """Check if a client is actually reachable via TCP connection to ADB port.
    
    Args:
        client_ip: IP address of the client (without port)
        timeout: Connection timeout in seconds
    
    Returns:
        True if client is reachable, False otherwise
    """
    if not client_ip:
        return False
    
    # Remove port if present
    if ':' in client_ip:
        client_ip = client_ip.split(':')[0]
    
    # Try TCP connection to ADB port (5555) - most reliable for Android devices
    try:
        loop = asyncio.get_event_loop()
        
        async def check_port(ip: str, port: int, timeout: float) -> bool:
            try:
                # Use asyncio to check connectivity
                future = loop.create_connection(
                    asyncio.Protocol,
                    ip,
                    port
                )
                # Wait for connection with timeout
                transport, protocol = await asyncio.wait_for(future, timeout=timeout)
                transport.close()
                return True
            except Exception:
                return False
        
        # Check ADB port (5555) - most reliable for Android devices
        adb_reachable = await check_port(client_ip, 5555, timeout)
        if adb_reachable:
            return True
        
        # Check Plex client port (32500) as fallback
        plex_reachable = await check_port(client_ip, 32500, timeout)
        if plex_reachable:
            return True
        
        return False
    except Exception as e:
        print(f"Error checking connectivity to {client_ip}: {str(e)}")
        return False
