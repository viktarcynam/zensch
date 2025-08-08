#!/usr/bin/env python3
"""
Example usage of the Schwab API client with JSON string requests.
This script demonstrates how to use JSON strings to communicate with the server.
"""
import json
import time
from client import SchwabClient
from json_parser import json_parser

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

def demonstrate_templates():
    """Demonstrate JSON request templates."""
    print_section("JSON Request Templates")
    
    # Get all available templates
    templates_result = json_parser.get_all_templates()
    
    if templates_result['success']:
        print("Available actions and their JSON templates:")
        for action, template in templates_result['templates'].items():
            print(f"\n{action.upper()}:")
            print(json.dumps(template, indent=2))
    else:
        print("Error getting templates:", templates_result.get('error'))

def demonstrate_validation():
    """Demonstrate JSON request validation."""
    print_section("JSON Request Validation")
    
    # Test valid JSON requests
    valid_requests = [
        '{"action": "ping"}',
        '{"action": "test_connection"}',
        '{"action": "get_linked_accounts"}',
        '{"action": "get_positions", "account_hash": "ABC123"}',
        '{"action": "get_positions_by_symbol", "symbol": "AAPL"}',
        '''
        {
            "action": "initialize_credentials",
            "app_key": "test_key",
            "app_secret": "test_secret",
            "callback_url": "https://127.0.0.1"
        }
        '''
    ]
    
    print("Testing valid JSON requests:")
    for i, json_str in enumerate(valid_requests, 1):
        print(f"\n{i}. Testing: {json_str.strip()}")
        result = json_parser.format_request(json_str)
        if result['success']:
            print("✓ Valid - Formatted request:")
            print(json.dumps(result['request'], indent=2))
        else:
            print("✗ Invalid:", result.get('error'))
    
    # Test invalid JSON requests
    invalid_requests = [
        '{"invalid": "json"}',  # Missing action
        '{"action": "invalid_action"}',  # Invalid action
        '{"action": "get_positions_by_symbol"}',  # Missing required symbol
        '{"action": "initialize_credentials", "app_key": ""}',  # Empty required field
        'invalid json string',  # Invalid JSON
        '',  # Empty string
    ]
    
    print("\n" + "="*40)
    print("Testing invalid JSON requests:")
    for i, json_str in enumerate(invalid_requests, 1):
        print(f"\n{i}. Testing: {json_str}")
        result = json_parser.format_request(json_str)
        if result['success']:
            print("✓ Unexpectedly valid")
        else:
            print("✗ Invalid (as expected):", result.get('error'))

def demonstrate_client_json():
    """Demonstrate client usage with JSON strings."""
    print_section("Client Usage with JSON Strings")
    
    client = SchwabClient()
    
    try:
        if not client.connect():
            print("Failed to connect to server. Make sure the server is running.")
            return
        
        # Test ping with JSON string
        print("1. Ping server using JSON string:")
        ping_json = '{"action": "ping"}'
        response = client.send_request(ping_json)
        print_response(response)
        
        # Test connection with JSON string
        print("\n2. Test connection using JSON string:")
        test_json = '{"action": "test_connection"}'
        response = client.send_request(test_json)
        print_response(response)
        
        # Test get positions with JSON string (will fail without credentials)
        print("\n3. Get positions using JSON string:")
        positions_json = '{"action": "get_positions"}'
        response = client.send_request(positions_json)
        print_response(response)
        
        # Test get positions by symbol with JSON string
        print("\n4. Get positions by symbol using JSON string:")
        symbol_json = '{"action": "get_positions_by_symbol", "symbol": "AAPL"}'
        response = client.send_request(symbol_json)
        print_response(response)
        
        # Test validation without sending
        print("\n5. Validate JSON without sending:")
        sample_json = '''
        {
            "action": "get_account_details",
            "account_hash": "test123",
            "include_positions": true
        }
        '''
        validation = client.validate_json_request(sample_json)
        print_response(validation, "Validation Result")
        
    except Exception as e:
        print(f"Error during demonstration: {str(e)}")
    finally:
        client.disconnect()

def demonstrate_interactive_json():
    """Interactive demonstration where user can input JSON."""
    print_section("Interactive JSON Request Testing")
    
    client = SchwabClient()
    
    try:
        if not client.connect():
            print("Failed to connect to server. Make sure the server is running.")
            return
        
        print("Enter JSON requests to send to the server.")
        print("Type 'templates' to see available templates.")
        print("Type 'quit' to exit.")
        
        while True:
            print("\n" + "-"*40)
            user_input = input("Enter JSON request: ").strip()
            
            if user_input.lower() == 'quit':
                break
            elif user_input.lower() == 'templates':
                templates = client.get_all_templates()
                if templates['success']:
                    for action, template in templates['templates'].items():
                        print(f"\n{action}:")
                        print(json.dumps(template, indent=2))
                continue
            elif not user_input:
                continue
            
            # Validate first
            validation = client.validate_json_request(user_input)
            if not validation['success']:
                print("❌ Invalid JSON request:")
                print(json.dumps(validation, indent=2))
                continue
            
            # Send request
            print("✅ Valid JSON. Sending to server...")
            response = client.send_request(user_input)
            print_response(response, "Server Response")
    
    except KeyboardInterrupt:
        print("\nInteractive session interrupted.")
    except Exception as e:
        print(f"Error during interactive session: {str(e)}")
    finally:
        client.disconnect()

def main():
    """Main demonstration function."""
    print("Schwab API Client - JSON String Request Demo")
    print("Make sure the server is running before executing this script!")
    
    # Run demonstrations
    demonstrate_templates()
    demonstrate_validation()
    demonstrate_client_json()
    
    # Ask if user wants interactive mode
    print("\n" + "="*60)
    interactive = input("Would you like to try interactive JSON mode? (y/n): ").lower().strip()
    if interactive == 'y':
        demonstrate_interactive_json()
    
    print("\n" + "="*60)
    print("JSON Client Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("✓ JSON request templates for all actions")
    print("✓ JSON request validation")
    print("✓ Client accepts both dict and JSON string requests")
    print("✓ Error handling for invalid JSON")
    print("✓ Interactive JSON request testing")

if __name__ == "__main__":
    main()