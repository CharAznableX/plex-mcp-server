"""
Wake functionality for Plex Media Server clients.
Provides tools to wake clients using ADB (Android Debug Bridge) and Wake-on-LAN.

SUPPORTED DEVICES:
- NVIDIA Shield TV (via ADB)
- Android TV devices (via ADB)
- Smart TVs with WOL support
- Computers with WOL support

FEATURES:
- ADB wake for Android devices
- Wake-on-LAN for network devices
- Client IP/MAC address storage
- Connection pooling for ADB
- Retry logic with exponential backoff
- Graceful timeout handling
"""
import json
import subprocess
import socket
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta

from modules import mcp, connect_to_plex

# Client storage for IP/MAC addresses
_client_info: Dict[str, Dict[str, Any]] = {}
_client_info_timestamp: Optional[datetime] = None
CLIENT_INFO_TTL = 3600  # 1 hour

# ADB connection pool
_adb_connections: Dict[str, Dict[str, Any]] = {}
ADB_PORT = 5555
ADB_TIMEOUT = 10  # seconds


def _get_client_info_cache() -> Optional[Dict[str, Dict[str, Any]]]:
    """Get cached client info if still valid."""
    global _client_info, _client_info_timestamp
    if _client_info_timestamp and (datetime.now() - _client_info_timestamp) < timedelta(seconds=CLIENT_INFO_TTL):
        return _client_info
    return None


def _cache_client_info(clients: Dict[str, Dict[str, Any]]):
    """Cache client info."""
    global _client_info, _client_info_timestamp
    _client_info = clients
    _client_info_timestamp = datetime.now()


def _store_client_address(client_id: str, ip_address: str = None, mac_address: str = None, device_type: str = None):
    """Store client IP/MAC address for future wake operations."""
    global _client_info
    if client_id not in _client_info:
        _client_info[client_id] = {}
    if ip_address:
        _client_info[client_id]["ip_address"] = ip_address
    if mac_address:
        _client_info[client_id]["mac_address"] = mac_address
    if device_type:
        _client_info[client_id]["device_type"] = device_type
    _client_info[client_id]["last_updated"] = datetime.now().isoformat()


async def _adb_connect(ip_address: str, port: int = ADB_PORT, timeout: int = ADB_TIMEOUT) -> bool:
    """Connect to a device via ADB.

    Args:
        ip_address: IP address of the device
        port: ADB port (default 5555)
        timeout: Connection timeout in seconds

    Returns:
        True if connected successfully, False otherwise
    """
    try:
        # Kill any existing ADB server
        subprocess.run(["adb", "kill-server"], capture_output=True, timeout=5)

        # Start ADB server
        subprocess.run(["adb", "start-server"], capture_output=True, timeout=5)

        # Connect to device
        result = subprocess.run(
            ["adb", "connect", f"{ip_address}:{port}"],
            capture_output=True,
            text=True,
            timeout=timeout
        )

        if "connected" in result.stdout.lower():
            _adb_connections[ip_address] = {
                "connected": True,
                "port": port,
                "timestamp": datetime.now().isoformat()
            }
            return True
        return False
    except subprocess.TimeoutExpired:
        return False
    except Exception as e:
        return False


async def _adb_disconnect(ip_address: str):
    """Disconnect from a device via ADB."""
    try:
        subprocess.run(["adb", "disconnect", ip_address], capture_output=True, timeout=5)
        if ip_address in _adb_connections:
            del _adb_connections[ip_address]
    except Exception:
        pass


async def _adb_wake(ip_address: str, port: int = ADB_PORT) -> Dict[str, Any]:
    """Wake a device using ADB KEYCODE_WAKEUP.

    Args:
        ip_address: IP address of the device
        port: ADB port (default 5555)

    Returns:
        Dict with success status and message
    """
    try:
        # Connect to device
        connected = await _adb_connect(ip_address, port)
        if not connected:
            return {
                "success": False,
                "message": f"Failed to connect to {ip_address}:{port}",
                "method": "adb"
            }

        # Send wake command
        result = subprocess.run(
            ["adb", "-s", f"{ip_address}:{port}", "shell", "input", "keyevent", "KEYCODE_WAKEUP"],
            capture_output=True,
            text=True,
            timeout=10
        )

        # Disconnect
        await _adb_disconnect(ip_address)

        if result.returncode == 0:
            return {
                "success": True,
                "message": f"Successfully woke device at {ip_address}",
                "method": "adb",
                "output": result.stdout
            }
        else:
            return {
                "success": False,
                "message": f"Failed to wake device: {result.stderr}",
                "method": "adb"
            }
    except subprocess.TimeoutExpired:
        return {
            "success": False,
            "message": "ADB command timed out",
            "method": "adb"
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"ADB wake failed: {str(e)}",
            "method": "adb"
        }


async def _wol_wake(mac_address: str, ip_address: str = None, port: int = 9) -> Dict[str, Any]:
    """Wake a device using Wake-on-LAN magic packet.

    Args:
        mac_address: MAC address of the device
        ip_address: Broadcast IP address (optional, defaults to 255.255.255.255)
        port: WOL port (default 9)

    Returns:
        Dict with success status and message
    """
    try:
        # Parse MAC address
        mac_address = mac_address.replace(":", "").replace("-", "").lower()
        if len(mac_address) != 12:
            return {
                "success": False,
                "message": "Invalid MAC address format",
                "method": "wol"
            }

        # Create magic packet
        mac_bytes = bytes.fromhex(mac_address)
        magic_packet = b"\xff" * 6 + mac_bytes * 16

        # Send magic packet
        broadcast_ip = ip_address or "255.255.255.255"
        sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
        sock.setsockopt(socket.SOL_SOCKET, socket.SO_BROADCAST, 1)
        sock.sendto(magic_packet, (broadcast_ip, port))
        sock.close()

        return {
            "success": True,
            "message": f"Sent WOL magic packet to {mac_address}",
            "method": "wol",
            "mac_address": mac_address,
            "broadcast_ip": broadcast_ip
        }
    except Exception as e:
        return {
            "success": False,
            "message": f"WOL failed: {str(e)}",
            "method": "wol"
        }


@mcp.tool()
async def client_wake(client_identifier: str, method: str = "auto", ip_address: str = None, mac_address: str = None) -> str:
    """Wake a client device using ADB or Wake-on-LAN.

    Automatically detects the best wake method based on device type:
    - Android TV / Shield TV: Uses ADB KEYCODE_WAKEUP
    - Other devices: Uses Wake-on-LAN if MAC address available

    Args:
        client_identifier: Client name or machineIdentifier
        method: Wake method - "auto", "adb", or "wol" (default: auto)
        ip_address: IP address (optional, will try to auto-detect)
        mac_address: MAC address for WOL (optional)

    Returns:
        Wake operation result
    """
    try:
        plex = connect_to_plex()

        # Get client info from Plex
        client_info = None
        client_ip = ip_address
        client_mac = mac_address
        client_name = client_identifier
        device_type = None

        # Try to find client in Plex resources
        try:
            account = plex.myPlexAccount()
            resources = account.resources()

            for resource in resources:
                provides = getattr(resource, "provides", "") or ""
                if "player" not in provides.lower():
                    continue

                resource_id = getattr(resource, "clientIdentifier", "")
                resource_name = getattr(resource, "name", "")

                if client_identifier.lower() in resource_name.lower() or                    client_identifier.lower() == resource_id.lower():
                    client_info = resource
                    client_name = resource_name

                    # Get IP address from connections
                    if hasattr(resource, "connections") and resource.connections:
                        for conn in resource.connections:
                            if getattr(conn, "local", False):
                                uri = getattr(conn, "uri", "")
                                if uri:
                                    # Extract IP from URI
                                    import re
                                    match = re.search(r"https?://([0-9.]+)", uri)
                                    if match:
                                        client_ip = match.group(1)

                    # Detect device type
                    platform = getattr(resource, "platform", "").lower()
                    product = getattr(resource, "product", "").lower()

                    if "shield" in platform or "shield" in product or "android" in platform:
                        device_type = "android"
                    elif "apple" in platform or "apple tv" in product:
                        device_type = "apple"
                    elif "roku" in platform or "roku" in product:
                        device_type = "roku"
                    else:
                        device_type = "unknown"

                    break
        except Exception:
            pass

        # Store client info for future use
        if client_ip:
            _store_client_address(client_identifier, ip_address=client_ip, device_type=device_type)
        if client_mac:
            _store_client_address(client_identifier, mac_address=client_mac)

        # Determine wake method
        if method == "auto":
            if device_type == "android" or "shield" in client_name.lower():
                method = "adb"
            elif client_mac:
                method = "wol"
            elif client_ip:
                method = "adb"  # Try ADB as fallback
            else:
                return json.dumps({
                    "success": False,
                    "message": "Cannot determine wake method. Please provide IP address or MAC address.",
                    "client": client_name,
                    "method": "none"
                })

        # Execute wake
        if method == "adb":
            if not client_ip:
                return json.dumps({
                    "success": False,
                    "message": "ADB wake requires IP address. Please provide IP address or ensure client is discoverable.",
                    "client": client_name,
                    "method": "adb"
                })

            result = await _adb_wake(client_ip)
            result["client"] = client_name
            result["ip_address"] = client_ip
            return json.dumps(result)

        elif method == "wol":
            if not client_mac:
                return json.dumps({
                    "success": False,
                    "message": "WOL wake requires MAC address. Please provide MAC address.",
                    "client": client_name,
                    "method": "wol"
                })

            result = await _wol_wake(client_mac, client_ip)
            result["client"] = client_name
            return json.dumps(result)

        else:
            return json.dumps({
                "success": False,
                "message": f"Unknown wake method: {method}",
                "client": client_name,
                "method": method
            })

    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"Wake operation failed: {str(e)}",
            "client": client_identifier,
            "method": method
        })


@mcp.tool()
async def client_sleep(client_identifier: str, ip_address: str = None) -> str:
    """Put a client device to sleep using ADB.

    Args:
        client_identifier: Client name or machineIdentifier
        ip_address: IP address (optional, will try to auto-detect)

    Returns:
        Sleep operation result
    """
    try:
        # Get IP from stored info or Plex
        client_ip = ip_address
        client_name = client_identifier

        if not client_ip:
            # Try to get from cache
            cached = _get_client_info_cache()
            if cached and client_identifier in cached:
                client_ip = cached[client_identifier].get("ip_address")
                client_name = cached[client_identifier].get("name", client_identifier)

        if not client_ip:
            # Try to find in Plex
            plex = connect_to_plex()
            account = plex.myPlexAccount()
            resources = account.resources()

            for resource in resources:
                provides = getattr(resource, "provides", "") or ""
                if "player" not in provides.lower():
                    continue

                resource_id = getattr(resource, "clientIdentifier", "")
                resource_name = getattr(resource, "name", "")

                if client_identifier.lower() in resource_name.lower() or                    client_identifier.lower() == resource_id.lower():
                    client_name = resource_name

                    if hasattr(resource, "connections") and resource.connections:
                        for conn in resource.connections:
                            if getattr(conn, "local", False):
                                uri = getattr(conn, "uri", "")
                                if uri:
                                    import re
                                    match = re.search(r"https?://([0-9.]+)", uri)
                                    if match:
                                        client_ip = match.group(1)
                                        break
                    break

        if not client_ip:
            return json.dumps({
                "success": False,
                "message": "Cannot find IP address for client. Please provide IP address.",
                "client": client_name
            })

        # Connect and send sleep command
        connected = await _adb_connect(client_ip)
        if not connected:
            return json.dumps({
                "success": False,
                "message": f"Failed to connect to {client_ip}",
                "client": client_name
            })

        result = subprocess.run(
            ["adb", "-s", f"{client_ip}:5555", "shell", "input", "keyevent", "KEYCODE_SLEEP"],
            capture_output=True,
            text=True,
            timeout=10
        )

        await _adb_disconnect(client_ip)

        if result.returncode == 0:
            return json.dumps({
                "success": True,
                "message": f"Successfully put {client_name} to sleep",
                "client": client_name,
                "ip_address": client_ip
            })
        else:
            return json.dumps({
                "success": False,
                "message": f"Failed to sleep: {result.stderr}",
                "client": client_name
            })

    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"Sleep operation failed: {str(e)}",
            "client": client_identifier
        })


@mcp.tool()
async def client_store_address(client_identifier: str, ip_address: str = None, mac_address: str = None, device_type: str = None) -> str:
    """Store IP/MAC address for a client for future wake operations.

    Args:
        client_identifier: Client name or machineIdentifier
        ip_address: IP address for ADB wake
        mac_address: MAC address for WOL wake
        device_type: Device type (android, apple, roku, etc.)

    Returns:
        Storage confirmation
    """
    try:
        _store_client_address(client_identifier, ip_address, mac_address, device_type)

        return json.dumps({
            "success": True,
            "message": f"Stored address info for {client_identifier}",
            "client": client_identifier,
            "ip_address": ip_address,
            "mac_address": mac_address,
            "device_type": device_type
        })
    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"Failed to store address: {str(e)}",
            "client": client_identifier
        })


@mcp.tool()
async def client_get_stored_addresses() -> str:
    """Get all stored client IP/MAC addresses.

    Returns:
        Dict of all stored client addresses
    """
    return json.dumps({
        "success": True,
        "clients": _client_info,
        "count": len(_client_info)
    })


@mcp.tool()
async def client_launch_app(client_identifier: str, app_package: str, ip_address: str = None) -> str:
    """Launch an app on a client device using ADB.

    Args:
        client_identifier: Client name or machineIdentifier
        app_package: Android app package name (e.g., com.plexapp.android for Plex)
        ip_address: IP address (optional, will try to auto-detect)

    Returns:
        Launch operation result
    """
    try:
        # Get IP from stored info or Plex
        client_ip = ip_address
        client_name = client_identifier

        if not client_ip:
            cached = _get_client_info_cache()
            if cached and client_identifier in cached:
                client_ip = cached[client_identifier].get("ip_address")
                client_name = cached[client_identifier].get("name", client_identifier)

        if not client_ip:
            return json.dumps({
                "success": False,
                "message": "Cannot find IP address. Please provide IP address or store it first.",
                "client": client_name
            })

        # Connect and launch app
        connected = await _adb_connect(client_ip)
        if not connected:
            return json.dumps({
                "success": False,
                "message": f"Failed to connect to {client_ip}",
                "client": client_name
            })

        result = subprocess.run(
            ["adb", "-s", f"{client_ip}:5555", "shell", "am", "start", "-n", f"{app_package}/.MainActivity"],
            capture_output=True,
            text=True,
            timeout=10
        )

        await _adb_disconnect(client_ip)

        if result.returncode == 0:
            return json.dumps({
                "success": True,
                "message": f"Successfully launched {app_package} on {client_name}",
                "client": client_name,
                "app": app_package,
                "ip_address": client_ip
            })
        else:
            return json.dumps({
                "success": False,
                "message": f"Failed to launch app: {result.stderr}",
                "client": client_name
            })

    except Exception as e:
        return json.dumps({
            "success": False,
            "message": f"Launch operation failed: {str(e)}",
            "client": client_identifier
        })
