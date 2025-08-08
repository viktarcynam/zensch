#!/usr/bin/env python3
"""
Demonstration of starting the server without credentials and initializing them later.
This script shows the complete workflow for credential-less startup.
"""
import time
import threading
import json
from server import SchwabServer
from client import SchwabClient

def print_section(title: str):
    """Print a formatted section header."""
    print(f"\n{'='*60}")
    print(f"{title}")
    print(f"{'='*60}")

def print_response(response: dict, title: str = "Response"):
    """Print a formatted response."""
    print(f"\n{title}:")
    print("-" * 40)
    print(json.dumps(response, indent=2))

def demonstrate_server_without_creds():
    """Demonstrate starting server without credentials."""
    print_section("Starting Server Without Credentials")
    
    # Start server without credentials
    server = SchwabServer(host='localhost', port=3461)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(1)
    
    print("✓ Server started successfully without credentials")
    print(f"  Server running on localhost:3461")
    print("  Server is ready to accept connections")
    print("  Credentials can be initialized later via client")
    
    return server

def demonstrate_client_connection_before_creds():
    """Demonstrate client connection before credentials are set."""
    print_section("Client Connection Before Credentials")
    
    client = SchwabClient(host='localhost', port=3461)
    
    try:
        if client.connect():
            print("✓ Client connected successfully to server")
            
            # Test ping (should work without credentials)
            print("\n1. Testing ping (should work):")
            response = client.send_request('{"action": "ping"}')
            print_response(response)
            
            # Test API call (should fail without credentials)
            print("\n2. Testing API call without credentials (should fail):")
            response = client.send_request('{"action": "get_linked_accounts"}')
            print_response(response)
            
            return client
        else:
            print("✗ Failed to connect to server")
            return None
    except Exception as e:
        print(f"✗ Connection error: {str(e)}")
        return None

def demonstrate_credential_initialization():
    """Demonstrate different ways to initialize credentials."""
    print_section("Credential Initialization Methods")
    
    client = SchwabClient(host='localhost', port=3461)
    
    if not client.connect():
        print("✗ Failed to connect to server")
        return False
    
    print("The following examples show different ways to initialize credentials.")
    print("(Using dummy credentials for demonstration)")
    
    # Method 1: Traditional client method
    print("\n1. Using traditional client method:")
    print("   client.initialize_credentials(app_key, app_secret)")
    response = client.initialize_credentials(
        app_key="dummy_app_key_for_demo",
        app_secret="dummy_app_secret_for_demo"
    )
    print_response(response, "Initialization Response")
    
    # Method 2: JSON string
    print("\n2. Using JSON string:")
    print('   client.send_request(\'{"action": "initialize_credentials", ...}\')')
    # Note: This would overwrite the previous credentials if it worked
    json_creds = '''
    {
        "action": "initialize_credentials",
        "app_key": "dummy_key_json",
        "app_secret": "dummy_secret_json",
        "callback_url": "https://127.0.0.1"
    }
    '''
    validation = client.validate_json_request(json_creds)
    print_response(validation, "JSON Validation (not sent)")
    
    # Method 3: File-based
    print("\n3. Using file + JSON combination:")
    print('   client.send_request("base_credentials.json", \'{"app_key": "...", "app_secret": "..."}\')')
    file_validation = client.validate_request_args(
        "example_requests/base_credentials.json",
        '{"app_key": "dummy_file_key"}',
        '{"app_secret": "dummy_file_secret"}'
    )
    print_response(file_validation, "File + JSON Validation (not sent)")
    
    client.disconnect()
    return True

def demonstrate_post_initialization_usage():
    """Demonstrate using the server after credentials are initialized."""
    print_section("Post-Initialization Usage")
    
    client = SchwabClient(host='localhost', port=3461)
    
    if not client.connect():
        print("✗ Failed to connect to server")
        return
    
    print("After credentials are initialized, you can use all API functions:")
    print("(These will fail with dummy credentials, but show the workflow)")
    
    # Test various API calls
    api_calls = [
        ('{"action": "test_connection"}', "Test API Connection"),
        ('{"action": "get_linked_accounts"}', "Get Linked Accounts"),
        ('{"action": "get_positions"}', "Get All Positions"),
        ('{"action": "get_positions_by_symbol", "symbol": "AAPL"}', "Get AAPL Positions"),
        ('{"action": "get_account_details"}', "Get Account Details"),
    ]
    
    for json_request, description in api_calls:
        print(f"\n{description}:")
        response = client.send_request(json_request)
        print_response(response)
    
    client.disconnect()

def demonstrate_workflow_summary():
    """Show a summary of the complete workflow."""
    print_section("Complete Workflow Summary")
    
    workflow_steps = [
        "1. Start server without credentials",
        "   python start_server.py  # Choose option 2",
        "   # OR",
        "   python start_server_no_creds.py",
        "   # OR",
        "   python server.py  # Direct execution",
        "",
        "2. Connect client to server",
        "   client = SchwabClient()",
        "   client.connect()",
        "",
        "3. Initialize credentials (choose one method):",
        "   # Method A: Traditional",
        "   client.initialize_credentials(app_key, app_secret)",
        "",
        "   # Method B: JSON string",
        "   client.send_request('{\"action\": \"initialize_credentials\", ...}')",
        "",
        "   # Method C: File-based",
        "   client.send_request('base_creds.json', '{\"app_key\": \"...\", \"app_secret\": \"...\"}')",
        "",
        "4. Use API functions normally",
        "   client.get_linked_accounts()",
        "   client.get_positions()",
        "   # etc.",
        "",
        "5. Server remains running with credentials until stopped",
    ]
    
    for step in workflow_steps:
        print(step)

def main():
    """Main demonstration function."""
    print("Schwab API Server - No Credentials Startup Demo")
    print("This demo shows how to start the server without credentials")
    print("and initialize them later via the client.")
    
    try:
        # Start server without credentials
        server = demonstrate_server_without_creds()
        
        # Show client connection before credentials
        client = demonstrate_client_connection_before_creds()
        if client:
            client.disconnect()
        
        # Show credential initialization methods
        demonstrate_credential_initialization()
        
        # Show post-initialization usage
        demonstrate_post_initialization_usage()
        
        # Show workflow summary
        demonstrate_workflow_summary()
        
        # Stop server
        server.stop()
        
    except Exception as e:
        print(f"Demo error: {str(e)}")
    
    print("\n" + "="*60)
    print("No Credentials Startup Demo Complete!")
    print("\nKey Benefits:")
    print("✓ Server can start without requiring credentials upfront")
    print("✓ Credentials can be provided later via multiple methods")
    print("✓ Useful for automated deployments and testing")
    print("✓ Supports dynamic credential management")
    print("✓ Server remains running once credentials are set")

if __name__ == "__main__":
    main()