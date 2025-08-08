# Schwab API Client-Server System

A Python application that provides a TCP server-client architecture for accessing the Charles Schwab API using the `schwabdev` library. The server runs in the background and handles authentication, while clients can connect via TCP to retrieve account information and positions.

## Features

- **Background Server**: Runs as a TCP server on port 3456
- **Authentication Management**: Handles Schwab API OAuth authentication and token management
- **Account Services**: Retrieve account details, balances, and summaries
- **Position Services**: Get position information across accounts or filtered by symbol
- **JSON Communication**: All communication between client and server uses JSON messages
- **Logging**: Comprehensive logging for debugging and monitoring
- **Error Handling**: Robust error handling with detailed error messages

## Project Structure

```
├── config.py                    # Configuration settings and credentials
├── schwab_auth.py              # Schwab API authentication module
├── account_service.py          # Account information services
├── positions_service.py        # Position information services
├── server.py                   # TCP server implementation
├── client.py                   # TCP client implementation
├── json_parser.py              # JSON request parser and formatter
├── example_usage.py            # Example usage script
├── json_client_example.py      # JSON string usage examples
├── test_json_functionality.py  # JSON functionality tests
├── requirements.txt            # Python dependencies
└── README.md                  # This file
```

## Installation

1. **Install Dependencies**:
   ```bash
   pip install -r requirements.txt
   ```

2. **Get Schwab API Credentials**:
   - Register at [Charles Schwab Developer Portal](https://developer.schwab.com/)
   - Create an application to get your App Key and App Secret
   - Set up a callback URL (default: `https://127.0.0.1`)

## Usage

### 1. Start the Server

#### Option A: Interactive Startup (Recommended)
```bash
python start_server.py
```
Choose from three startup modes:
- **Mode 1**: Start with credentials (traditional - enter credentials upfront)
- **Mode 2**: Start without credentials (initialize later via client) **[NEW]**
- **Mode 3**: Auto-detect from environment variables

#### Option B: Direct Server Start
```bash
python server.py
```
Starts server directly, auto-detecting credentials from environment variables.

#### Option C: No-Credentials Startup **[NEW]**
```bash
python start_server_no_creds.py
```
Dedicated script for starting without credentials.

The server will start on `localhost:3456` by default. You can configure the host and port using environment variables:

```bash
export SERVER_HOST=localhost
export SERVER_PORT=3456
python start_server.py
```

### 2. Use the Client

#### Option A: Interactive Example
```bash
python example_usage.py
```

#### Option B: Programmatic Usage
```python
from client import SchwabClient

# Create client and connect
client = SchwabClient()
client.connect()

# Initialize credentials
response = client.initialize_credentials(
    app_key="your_app_key",
    app_secret="your_app_secret"
)

# Get account information
accounts = client.get_linked_accounts()
positions = client.get_positions()

# Disconnect
client.disconnect()
```

#### Option C: Context Manager
```python
from client import SchwabClient

with SchwabClient() as client:
    # Initialize credentials
    client.initialize_credentials("your_app_key", "your_app_secret")
    
    # Get data
    accounts = client.get_linked_accounts()
    positions = client.get_positions()
```

#### Option D: JSON String Requests
```python
from client import SchwabClient

with SchwabClient() as client:
    # Initialize credentials using JSON string
    creds_json = '''
    {
        "action": "initialize_credentials",
        "app_key": "your_app_key",
        "app_secret": "your_app_secret"
    }
    '''
    response = client.send_request(creds_json)
    
    # Get positions using JSON string
    positions_json = '{"action": "get_positions"}'
    positions = client.send_request(positions_json)
    
    # Get positions by symbol using JSON string
    symbol_json = '{"action": "get_positions_by_symbol", "symbol": "AAPL"}'
    aapl_positions = client.send_request(symbol_json)
```

#### Option E: File-Based Requests **[NEW]**
```python
from client import SchwabClient

with SchwabClient() as client:
    # Load request from JSON file
    response = client.send_request("requests/ping.json")
    
    # Combine file with additional JSON
    response = client.send_request(
        "requests/base_credentials.json",
        '{"app_key": "your_key"}',
        '{"app_secret": "your_secret"}'
    )
    
    # Mix file, dictionary, and JSON string
    response = client.send_request(
        {"action": "get_positions"},
        "overrides.json",
        '{"account_hash": "ABC123"}'
    )
    
    # Use dedicated file method
    response = client.send_from_file("request.json", additional_args...)
```

#### Option F: Initialize Credentials After Server Start **[NEW]**
If you started the server without credentials, you can initialize them later:

```python
from client import SchwabClient

with SchwabClient() as client:
    # Method 1: Traditional initialization
    response = client.initialize_credentials(
        app_key="your_app_key",
        app_secret="your_app_secret"
    )
    
    # Method 2: JSON string initialization
    creds_json = '''
    {
        "action": "initialize_credentials",
        "app_key": "your_app_key",
        "app_secret": "your_app_secret",
        "callback_url": "https://127.0.0.1"
    }
    '''
    response = client.send_request(creds_json)
    
    # Method 3: File-based initialization
    response = client.send_request(
        "example_requests/base_credentials.json",
        '{"app_key": "your_app_key"}',
        '{"app_secret": "your_app_secret"}'
    )
    
    # After initialization, use API normally
    accounts = client.get_linked_accounts()
    positions = client.get_positions()
```

## API Reference

### Server Actions

The server accepts JSON messages with the following actions:

#### Authentication
- **`initialize_credentials`**: Set up API credentials
  ```json
  {
    "action": "initialize_credentials",
    "app_key": "your_app_key",
    "app_secret": "your_app_secret",
    "callback_url": "https://127.0.0.1",
    "tokens_file": "tokens.json"
  }
  ```

#### Server Status
- **`ping`**: Check if server is running
- **`test_connection`**: Test connection to Schwab API

#### Account Information
- **`get_linked_accounts`**: Get all linked account numbers and hashes
- **`get_account_details`**: Get detailed account information
  ```json
  {
    "action": "get_account_details",
    "account_hash": "optional_specific_account",
    "include_positions": false
  }
  ```
- **`get_account_summary`**: Get account balances without positions

#### Position Information
- **`get_positions`**: Get all positions
  ```json
  {
    "action": "get_positions",
    "account_hash": "optional_specific_account"
  }
  ```
- **`get_positions_by_symbol`**: Get positions for a specific symbol
  ```json
  {
    "action": "get_positions_by_symbol",
    "symbol": "AAPL",
    "account_hash": "optional_specific_account"
  }
  ```

### Client Methods

The `SchwabClient` class provides the following methods:

#### Traditional Methods
- `ping()` - Ping the server
- `test_connection()` - Test Schwab API connection
- `initialize_credentials(app_key, app_secret, callback_url, tokens_file)` - Set credentials
- `get_linked_accounts()` - Get linked accounts
- `get_account_details(account_hash, include_positions)` - Get account details
- `get_account_summary(account_hash)` - Get account summary
- `get_positions(account_hash)` - Get positions
- `get_positions_by_symbol(symbol, account_hash)` - Get positions by symbol

#### JSON String Methods
- `send_request(*args)` - Send request (accepts files, JSON strings, dictionaries, or combinations)
- `send_json_request(json_string)` - Send JSON string request specifically
- `validate_json_request(json_string)` - Validate JSON request without sending
- `get_request_template(action)` - Get JSON template for specific action
- `get_all_templates()` - Get all available JSON templates

#### File-Based Methods **[NEW]**
- `send_from_file(filename, *additional_args)` - Send request from file with optional additional arguments
- `load_json_file(filename)` - Load and validate JSON from file
- `validate_request_args(*args)` - Validate any combination of arguments without sending

#### Argument Types Supported
- **Dictionary**: `{"action": "ping"}`
- **JSON String**: `'{"action": "ping"}'` (must contain ':' character)
- **Filename**: `"request.json"` (no ':' character, file must exist)
- **Combinations**: Mix any of the above types

#### JSON Request Templates

You can get templates for all actions:

```python
client = SchwabClient()
templates = client.get_all_templates()
for action, template in templates['templates'].items():
    print(f"{action}: {json.dumps(template, indent=2)}")
```

Example templates:
```json
{
  "action": "get_positions_by_symbol",
  "symbol": "<required_symbol>",
  "account_hash": "<optional_account_hash>"
}
```

#### File-Based Request Examples **[NEW]**

Create JSON files for reusable requests:

**ping.json**:
```json
{
  "action": "ping"
}
```

**base_credentials.json**:
```json
{
  "action": "initialize_credentials",
  "callback_url": "https://127.0.0.1",
  "tokens_file": "tokens.json"
}
```

**base_symbol_request.json**:
```json
{
  "action": "get_positions_by_symbol"
}
```

Usage examples:
```python
# Simple file request
client.send_request("ping.json")

# File + additional JSON
client.send_request("base_credentials.json", '{"app_key": "key", "app_secret": "secret"}')

# File + symbol override
client.send_request("base_symbol_request.json", '{"symbol": "AAPL"}')

# Multiple combinations
client.send_request(
    {"action": "get_account_details"},
    "overrides.json", 
    '{"include_positions": true}'
)
```

## JSON Parser Module

The `json_parser.py` module provides JSON request parsing and validation:

### Features
- **JSON Parsing**: Parse JSON strings into Python dictionaries
- **Request Validation**: Validate requests for required fields and correct format
- **Template Generation**: Generate JSON templates for all available actions
- **Parameter Validation**: Validate parameter types and values
- **Error Handling**: Comprehensive error messages for invalid requests

### Usage
```python
from json_parser import json_parser

# Parse and validate JSON string
result = json_parser.format_request('{"action": "ping"}')
if result['success']:
    formatted_request = result['request']
else:
    print(f"Error: {result['error']}")

# Get template for specific action
template = json_parser.create_request_template('get_positions_by_symbol')
print(template['json_template'])

# Get all templates
all_templates = json_parser.get_all_templates()
```

### Validation Rules
- **Required Fields**: `action` field is always required
- **Valid Actions**: Only predefined actions are accepted
- **Required Parameters**: Some actions require specific parameters (e.g., `symbol` for `get_positions_by_symbol`)
- **Parameter Types**: Boolean parameters are automatically converted from strings
- **Empty Values**: Required parameters cannot be empty or whitespace-only

## Configuration

### Environment Variables

You can configure the application using environment variables:

```bash
# Schwab API Credentials
export SCHWAB_APP_KEY=your_app_key
export SCHWAB_APP_SECRET=your_app_secret
export SCHWAB_CALLBACK_URL=https://127.0.0.1
export SCHWAB_TOKENS_FILE=tokens.json

# Server Configuration
export SERVER_HOST=localhost
export SERVER_PORT=3456
export REQUEST_TIMEOUT=10
```

### Configuration File

Modify `config.py` to change default settings:

```python
from config import config

# Update credentials programmatically
config.update_credentials(
    app_key="your_app_key",
    app_secret="your_app_secret"
)
```

## Authentication Flow

1. **First Time Setup**: When you first initialize credentials, the schwabdev library will:
   - Open a web browser for OAuth authentication
   - Prompt you to log in to your Schwab account
   - Capture the authorization code
   - Exchange it for access and refresh tokens
   - Save tokens to the specified file

2. **Subsequent Uses**: The library will automatically:
   - Load saved tokens from file
   - Refresh tokens when they expire
   - Handle re-authentication if needed

## Error Handling

All responses include error information:

```json
{
  "success": false,
  "error": "Error description",
  "timestamp": "2024-01-01T12:00:00.000000"
}
```

Common errors:
- **Authentication Failed**: Invalid credentials or expired tokens
- **Connection Error**: Server not running or network issues
- **API Error**: Schwab API returned an error
- **Invalid Request**: Malformed JSON or missing parameters

## Logging

The application logs to both console and file:
- **Server logs**: `schwab_server.log`
- **Log levels**: INFO, ERROR, DEBUG
- **Log format**: Timestamp, logger name, level, message

## Security Considerations

1. **Credentials**: Never hardcode credentials in source code
2. **Tokens**: The tokens file contains sensitive authentication data
3. **Network**: The TCP server runs on localhost by default
4. **HTTPS**: Schwab API requires HTTPS for callbacks

## Troubleshooting

### Common Issues

1. **"Server services not initialized"**
   - Solution: Call `initialize_credentials` first

2. **"Failed to authenticate with Schwab API"**
   - Check your app key and secret
   - Ensure callback URL matches your app registration
   - Check internet connection

3. **"Connection refused"**
   - Ensure the server is running
   - Check host and port configuration

4. **"Invalid JSON format"**
   - Ensure request is valid JSON
   - Check for proper escaping of strings

### Debug Mode

Enable debug logging:

```python
import logging
logging.basicConfig(level=logging.DEBUG)
```

## License

This project is for educational and personal use. Please comply with Charles Schwab's API terms of service.

## Disclaimer

This software is not affiliated with or endorsed by Charles Schwab. Use at your own risk and ensure compliance with all applicable terms of service and regulations.