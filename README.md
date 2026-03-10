# Plex MCP Server (Enhanced Fork)

A powerful Model-Context-Protocol (MCP) server for interacting with Plex Media Server. This is an enhanced fork of the original [plex-mcp-server](https://github.com/vladimir-tutin/plex-mcp-server) with significant improvements in client detection, device control, and security.

## ✨ What Makes This Fork Different

| Feature | Original Repo | This Fork |
|---------|---------------|-----------|
| Passive Client Detection | ❌ Only detects active streams | ✅ Detects all clients without active stream |
| Wake-on-LAN | ❌ | ✅ Wake network devices via WOL |
| ADB Wake for Android | ❌ | ✅ Wake Shield TV, Android TV via ADB |
| Client Caching | ❌ | ✅ 5-minute TTL caching |
| Multiple Discovery Methods | ❌ | ✅ myPlex + server + sessions |
| App Launch via ADB | ❌ | ✅ Launch apps on Android devices |
| **Security Module** | ❌ | ✅ Comprehensive security features |
| Input Validation | ❌ | ✅ Sanitization and validation |
| Rate Limiting | ❌ | ✅ 100 requests per 60 seconds |
| Audit Logging | ❌ | ✅ Security audit trail |
| Secure Error Handling | ❌ | ✅ No sensitive data leakage |

## 🚀 Key Improvements

### 1. Passive Client Detection
- **Problem**: Original only detected clients with active streams
- **Solution**: Multiple discovery methods work without active streams
- **Methods**: myPlexAccount.resources(), plex.clients(), session-based detection

### 2. Wake Module
- **ADB Wake**: Wake Android TV / Shield TV via ADB
- **Wake-on-LAN**: Wake network devices via magic packet
- **Client Storage**: Store IP/MAC addresses for clients
- **App Launch**: Launch apps on Android devices

### 3. Security Module
- **Input Validation**: Sanitize all inputs to prevent injection attacks
- **Rate Limiting**: Prevent API abuse (100 requests per 60 seconds)
- **Audit Logging**: Track all operations for security review
- **Secure Errors**: Never expose sensitive data in error messages

## Installation

### Option 1: Using uv (Recommended)

Run directly without installation:
```bash
uvx --from git+https://github.com/CharAznableX/plex-mcp-server.git plex-mcp-server --transport stdio --plex-url http://your-server:32400 --plex-token your-token
```

### Option 2: Install via pip

```bash
pip install git+https://github.com/CharAznableX/plex-mcp-server.git
```

### Option 3: Development / Source

```bash
git clone https://github.com/CharAznableX/plex-mcp-server.git
cd plex-mcp-server
pip install -e .
```

## Configuration

Set your Plex server URL and Token using one of these methods:

### 1. Command Line Arguments
```bash
plex-mcp-server --plex-url "http://192.168.1.10:32400" --plex-token "ABC123XYZ"
```

### 2. Environment Variables (.env)
Create a `.env` file in the current directory or `~/.config/plex-mcp-server/.env`:
```env
PLEX_URL=http://localhost:32400
PLEX_TOKEN=your-authentication-token
MCP_OAUTH_ENABLED=false
```

### 3. MCP Client Config
Example for Claude Desktop (`%APPDATA%/Claude/claude_desktop_config.json`):
```json
{
  "mcpServers": {
    "plex": {
      "command": "uvx",
      "args": [
        "--from",
        "git+https://github.com/CharAznableX/plex-mcp-server.git",
        "plex-mcp-server",
        "--transport",
        "stdio",
        "--plex-url",
        "http://your-server:32400",
        "--plex-token",
        "your-token"
      ]
    }
  }
}
```

## Command Reference

### Library Module
Tools for exploring and managing your Plex libraries.

| Command | Description | Parameters |
|---------|-------------|------------|
| `library_list` | Lists all available libraries. | None |
| `library_get_stats` | Gets statistics (count, size, types) for a library. | `library_name` |
| `library_refresh` | Triggers a metadata refresh for a library. | `library_name` |

### Client Module (Enhanced)
Tools for managing Plex clients with passive detection.

| Command | Description | Parameters |
|---------|-------------|------------|
| `client_list` | Lists all available clients (works without active stream). | `force_refresh` (optional) |
| `client_get_timeline` | Gets the current timeline for a client. | `client_identifier` |
| `client_set_parameters` | Sets parameters for a client. | `client_identifier`, `parameters` |

### Wake Module (NEW)
Tools for waking devices via ADB or Wake-on-LAN.

| Command | Description | Parameters |
|---------|-------------|------------|
| `client_wake` | Wake a device via ADB or Wake-on-LAN. | `client_identifier`, `method` (optional) |
| `client_sleep` | Put a device to sleep via ADB. | `client_identifier` |
| `client_store_address` | Store IP/MAC address for a client. | `client_identifier`, `ip_address`, `mac_address` (optional) |
| `client_get_stored_addresses` | Get stored addresses for all clients. | None |
| `client_launch_app` | Launch an app on an Android device. | `client_identifier`, `app_package` |

### Security Module (NEW)
Tools for security management.

| Command | Description | Parameters |
|---------|-------------|------------|
| `security_get_status` | Get security configuration and status. | None |
| `security_get_audit_log` | Get security audit log entries. | `limit` (optional), `client_id` (optional) |
| `security_get_rate_limits` | Get current rate limit status. | None |
| `security_clear_rate_limits` | Clear rate limits for a client. | `client_id` (optional) |
| `security_validate_input` | Validate and sanitize input. | `value`, `input_type` |

## ADB Setup for Android Wake

To use ADB wake functionality for Shield TV / Android TV:

```bash
# On Mac
brew install android-platform-tools

# On Linux
apt-get install android-tools-adb

# On Windows
# Download from https://developer.android.com/studio/releases/platform-tools
```

### Enable ADB on Shield TV

1. Go to Settings > Device Preferences > Developer Options
2. Enable "USB debugging"
3. Enable "Network debugging" (ADB over network)
4. Note your Shield TV IP address

### Test ADB Connection

```bash
adb connect 192.168.1.100:5555
adb shell input keyevent KEYCODE_WAKEUP
adb disconnect
```

## Security Features

### Input Validation
All inputs are validated and sanitized to prevent:
- SQL injection
- Script injection
- Command injection
- Path traversal

### Rate Limiting
- 100 requests per 60 seconds per client
- Automatic reset after window expires
- Configurable limits

### Audit Logging
- All operations logged with timestamp
- Client identifier tracking
- Success/failure status
- Maximum 1000 entries (configurable)

### Secure Error Handling
- No sensitive data in error messages
- Generic error messages for security
- Detailed logs for debugging

## Development

### Running Tests
```bash
python -m pytest tests/
```

### Code Style
```bash
black .
isort .
flake8
```

## Contributing

Contributions are welcome! Please feel free to submit a Pull Request.

## License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## Acknowledgments

- Original project by [Vladimir Tutin](https://github.com/vladimir-tutin/plex-mcp-server)
- Enhanced with passive client detection, wake functionality, and security features

## Changelog

### v1.1.0 (Enhanced Fork)
- Added passive client detection (works without active stream)
- Added Wake module with ADB and Wake-on-LAN support
- Added Security module with input validation, rate limiting, and audit logging
- Added client caching (5-minute TTL)
- Added multiple discovery methods
- Added app launch functionality for Android devices
- Improved error handling and security
