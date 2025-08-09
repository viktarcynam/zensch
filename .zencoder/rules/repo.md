---
description: Repository Information Overview
alwaysApply: true
---

# Schwab API Client-Server System Information

## Summary
A Python application that provides a TCP server-client architecture for accessing the Charles Schwab API using the `schwabdev` library. The server runs in the background and handles authentication, while clients can connect via TCP to retrieve account information, positions, quotes, and options data.

## Structure
- **Server Components**: `server.py`, `start_server.py`, `start_server_no_creds.py`
- **Client Components**: `client.py`, `example_usage.py`, `json_client_example.py`, `file_client_example.py`
- **Service Modules**: `account_service.py`, `positions_service.py`, `schwab_auth.py`, `quotes_service.py`, `options_service.py`
- **Utility Modules**: `json_parser.py`, `creds_manager.py`, `enhanced_tokens.py`, `config.py`
- **Example Data**: `example_requests/` directory with JSON request templates
- **Tests**: Multiple test files for different components

## Language & Runtime
**Language**: Python
**Version**: 3.13.2
**Package Manager**: pip

## Dependencies
**Main Dependencies**:
- schwabdev (>=2.5.0) - Charles Schwab API client library
- requests (>=2.25.0) - HTTP library for API calls
- websockets (>=10.0) - WebSocket client/server library
- PyYAML (>=6.0) - YAML parsing and generation

## Build & Installation
```bash
pip install -r requirements.txt
```

## Usage & Operations
**Server Start Commands**:
```bash
python start_server.py  # Interactive startup with credential options
python start_server_no_creds.py  # Start without credentials
python server.py  # Direct server start
```

**Client Usage**:
```bash
python example_usage.py  # Interactive example
python quotes_example.py  # Quotes feature example
python options_example.py  # Options feature example
```

## Testing
**Framework**: Built-in unittest (implicit from test structure)
**Test Files**: 
- `test_system.py` - Core system functionality tests
- `test_json_functionality.py` - JSON parsing tests
- `test_file_arguments.py` - File-based request tests
- `test_enhanced_tokens.py` - Token handling tests
- `test_token_detection.py` - Token detection tests
- `test_creds_yml.py` - YAML credentials tests

**Run Command**:
```bash
python test_system.py  # Run system tests
```

## Configuration
**Environment Variables**:
- `SCHWAB_APP_KEY`, `SCHWAB_APP_SECRET` - API credentials
- `SCHWAB_CALLBACK_URL` - OAuth callback URL
- `SERVER_HOST`, `SERVER_PORT` - Server configuration
- `REQUEST_TIMEOUT` - Client request timeout

**Configuration File**: `config.py` contains default settings and credential management

## Features
**Core Features**:
- Account information retrieval
- Position data retrieval
- Authentication management
- JSON-based communication

**New Features**:
- Stock quotes retrieval via `quotes_service.py`
- Options chain data via `options_service.py`
- Modular service architecture for easy extension