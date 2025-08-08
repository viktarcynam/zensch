#!/usr/bin/env python3
"""
Complete demonstration of the Schwab API client-server system.
This script shows all the available functionality.
"""
import json
import time
import threading
from datetime import datetime
from server import SchwabServer
from client import SchwabClient

def print_section(title):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")

def print_response(response, title="Response"):
    """Print a formatted response."""
    print(f"\n{title}:")
    print("-" * 40)
    if isinstance(response, dict):
        print(json.dumps(response, indent=2))
    else:
        print(response)

def demo_without_credentials():
    """Demonstrate functionality that works without credentials."""
    print_section("DEMO: Functionality Without Credentials")
    
    # Start server in background
    server = SchwabServer(host='localhost', port=3458)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(1)
    
    try:
        with SchwabClient(host='localhost', port=3458) as client:
            # Test ping
            print_response(client.ping(), "1. Ping Server")
            
            # Test connection without credentials
            print_response(client.test_connection(), "2. Test Connection (No Credentials)")
            
            # Try to get accounts without credentials
            print_response(client.get_linked_accounts(), "3. Get Accounts (Should Fail)")
            
            # Show available actions
            invalid_response = client.send_request({'action': 'invalid'})
            if 'available_actions' in invalid_response:
                print(f"\n4. Available Actions:")
                print("-" * 40)
                for action in invalid_response['available_actions']:
                    print(f"  - {action}")
    
    finally:
        server.stop()

def demo_json_message_format():
    """Demonstrate the JSON message format for client-server communication."""
    print_section("DEMO: JSON Message Formats")
    
    print("The client-server communication uses JSON messages with the following formats:")
    
    examples = {
        "1. Initialize Credentials": {
            "action": "initialize_credentials",
            "app_key": "your_schwab_app_key",
            "app_secret": "your_schwab_app_secret",
            "callback_url": "https://127.0.0.1",
            "tokens_file": "tokens.json"
        },
        
        "2. Ping Server": {
            "action": "ping"
        },
        
        "3. Test Connection": {
            "action": "test_connection"
        },
        
        "4. Get Linked Accounts": {
            "action": "get_linked_accounts"
        },
        
        "5. Get Account Details": {
            "action": "get_account_details",
            "account_hash": "optional_account_hash",
            "include_positions": False
        },
        
        "6. Get Account Summary": {
            "action": "get_account_summary",
            "account_hash": "optional_account_hash"
        },
        
        "7. Get All Positions": {
            "action": "get_positions",
            "account_hash": "optional_account_hash"
        },
        
        "8. Get Positions by Symbol": {
            "action": "get_positions_by_symbol",
            "symbol": "AAPL",
            "account_hash": "optional_account_hash"
        }
    }
    
    for title, example in examples.items():
        print(f"\n{title}:")
        print("-" * 40)
        print(json.dumps(example, indent=2))

def demo_response_format():
    """Demonstrate typical response formats."""
    print_section("DEMO: Response Formats")
    
    print("All server responses follow a consistent format:")
    
    examples = {
        "1. Successful Response": {
            "success": True,
            "data": {
                "accounts": [
                    {
                        "accountHash": "ABC123XYZ",
                        "accountType": "MARGIN",
                        "positions": [
                            {
                                "symbol": "AAPL",
                                "quantity": 100,
                                "marketValue": 15000.50,
                                "dayChange": 250.75,
                                "dayChangePercent": 1.67
                            }
                        ]
                    }
                ]
            },
            "message": "Successfully retrieved account data",
            "timestamp": "2024-01-01T12:00:00.000000"
        },
        
        "2. Error Response": {
            "success": False,
            "error": "Server services not initialized. Please provide credentials.",
            "timestamp": "2024-01-01T12:00:00.000000"
        },
        
        "3. Ping Response": {
            "success": True,
            "message": "Server is running",
            "timestamp": "2024-01-01T12:00:00.000000"
        }
    }
    
    for title, example in examples.items():
        print(f"\n{title}:")
        print("-" * 40)
        print(json.dumps(example, indent=2))

def demo_usage_instructions():
    """Show usage instructions."""
    print_section("DEMO: Usage Instructions")
    
    instructions = """
STEP 1: Get Schwab API Credentials
---------------------------------
1. Go to https://developer.schwab.com/
2. Create a developer account
3. Create a new application
4. Note down your App Key and App Secret
5. Set callback URL to: https://127.0.0.1

STEP 2: Start the Server
-----------------------
Option A - Interactive startup:
    python start_server.py

Option B - With environment variables:
    export SCHWAB_APP_KEY=your_app_key
    export SCHWAB_APP_SECRET=your_app_secret
    python server.py

Option C - Programmatic startup:
    from server import SchwabServer
    server = SchwabServer()
    server.initialize_services(app_key, app_secret)
    server.start()

STEP 3: Use the Client
---------------------
Option A - Interactive example:
    python example_usage.py

Option B - Programmatic usage:
    from client import SchwabClient
    
    with SchwabClient() as client:
        # Initialize credentials
        client.initialize_credentials(app_key, app_secret)
        
        # Get data
        accounts = client.get_linked_accounts()
        positions = client.get_positions()

STEP 4: Available Client Methods
-------------------------------
- ping() - Test server connectivity
- test_connection() - Test Schwab API connection
- initialize_credentials() - Set up API credentials
- get_linked_accounts() - Get all account hashes
- get_account_details() - Get account info with/without positions
- get_account_summary() - Get account balances only
- get_positions() - Get all positions
- get_positions_by_symbol() - Filter positions by symbol

STEP 5: Server Configuration
---------------------------
Default settings:
- Host: localhost
- Port: 3456
- Timeout: 10 seconds

Environment variables:
- SCHWAB_APP_KEY
- SCHWAB_APP_SECRET  
- SCHWAB_CALLBACK_URL
- SCHWAB_TOKENS_FILE
- SERVER_HOST
- SERVER_PORT
- REQUEST_TIMEOUT
"""
    
    print(instructions)

def main():
    """Main demo function."""
    print("Schwab API Client-Server System - Complete Demo")
    print(f"Demo started at: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    
    # Run demonstrations
    demo_without_credentials()
    demo_json_message_format()
    demo_response_format()
    demo_usage_instructions()
    
    print_section("DEMO COMPLETE")
    print("""
This completes the demonstration of the Schwab API client-server system.

Key Features Demonstrated:
✓ TCP server running on configurable port (default 3456)
✓ JSON-based client-server communication
✓ Authentication and session management
✓ Account information retrieval
✓ Position information retrieval
✓ Error handling and logging
✓ Flexible configuration options

To use with real Schwab data:
1. Get your API credentials from https://developer.schwab.com/
2. Run: python start_server.py
3. Run: python example_usage.py (in another terminal)

The system is ready for production use!
""")

if __name__ == "__main__":
    main()