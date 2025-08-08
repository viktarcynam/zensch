#!/usr/bin/env python3
"""
Example usage of the Schwab API client with file-based arguments.
This script demonstrates how to use JSON files and combine them with additional arguments.
"""
import json
import os
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

def demonstrate_file_loading():
    """Demonstrate loading JSON from files."""
    print_section("File Loading Examples")
    
    client = SchwabClient()
    
    # Show available example files
    if os.path.exists("example_requests"):
        print("Available example files:")
        for filename in os.listdir("example_requests"):
            if filename.endswith('.json'):
                print(f"  - example_requests/{filename}")
                
                # Load and show content
                result = client.load_json_file(f"example_requests/{filename}")
                if result['success']:
                    print(f"    Content: {json.dumps(result['data'], indent=6)}")
                else:
                    print(f"    Error: {result['error']}")
    else:
        print("No example_requests directory found. Creating example files...")
        create_example_files()

def demonstrate_argument_combinations():
    """Demonstrate different argument combination patterns."""
    print_section("Argument Combination Examples")
    
    client = SchwabClient()
    
    # Example 1: Single file
    print("\n1. Single file request:")
    print("   Usage: client.send_request('ping.json')")
    validation = client.validate_request_args("example_requests/ping.json")
    print_response(validation, "Validation Result")
    
    # Example 2: File + JSON string
    print("\n2. File + JSON string combination:")
    print("   Usage: client.send_request('base_symbol.json', '{\"symbol\": \"AAPL\"}')")
    validation = client.validate_request_args(
        "example_requests/base_symbol_request.json",
        '{"symbol": "AAPL"}'
    )
    print_response(validation, "Validation Result")
    
    # Example 3: File + multiple JSON strings
    print("\n3. File + multiple JSON strings:")
    print("   Usage: client.send_request('base_creds.json', '{\"app_key\": \"key\"}', '{\"app_secret\": \"secret\"}')")
    validation = client.validate_request_args(
        "example_requests/base_credentials.json",
        '{"app_key": "your_app_key"}',
        '{"app_secret": "your_app_secret"}'
    )
    print_response(validation, "Validation Result")
    
    # Example 4: Dictionary + file + JSON
    print("\n4. Dictionary + file + JSON combination:")
    print("   Usage: client.send_request({'action': 'get_positions'}, 'override.json', '{\"account_hash\": \"ABC\"}')")
    validation = client.validate_request_args(
        {"action": "get_positions"},
        '{"account_hash": "ABC123"}'
    )
    print_response(validation, "Validation Result")

def demonstrate_real_usage():
    """Demonstrate real usage scenarios."""
    print_section("Real Usage Scenarios")
    
    print("Make sure the server is running before executing these examples!")
    
    client = SchwabClient()
    
    try:
        if not client.connect():
            print("Failed to connect to server. Make sure the server is running.")
            return
        
        # Scenario 1: Simple ping from file
        print("\n1. Ping server using file:")
        response = client.send_request("example_requests/ping.json")
        print_response(response)
        
        # Scenario 2: Get positions by symbol (file + JSON)
        print("\n2. Get positions by symbol (combining file + JSON):")
        response = client.send_request(
            "example_requests/base_symbol_request.json",
            '{"symbol": "AAPL"}'
        )
        print_response(response)
        
        # Scenario 3: Account details with position override
        print("\n3. Account details with position override:")
        response = client.send_request(
            "example_requests/account_details.json",
            '{"include_positions": true}'
        )
        print_response(response)
        
        # Scenario 4: Using send_from_file method
        print("\n4. Using send_from_file method:")
        response = client.send_from_file(
            "example_requests/get_positions.json",
            '{"account_hash": "optional_hash"}'
        )
        print_response(response)
        
    except Exception as e:
        print(f"Error during demonstration: {str(e)}")
    finally:
        client.disconnect()

def demonstrate_credential_setup():
    """Demonstrate credential setup using files."""
    print_section("Credential Setup Example")
    
    print("This example shows how to set up credentials using file + JSON combination:")
    print("\n1. Create a base credentials file (base_credentials.json):")
    print(json.dumps({
        "action": "initialize_credentials",
        "callback_url": "https://127.0.0.1",
        "tokens_file": "tokens.json"
    }, indent=2))
    
    print("\n2. Combine with your actual credentials:")
    print("client.send_request(")
    print("    'base_credentials.json',")
    print("    '{\"app_key\": \"your_actual_app_key\"}',")
    print("    '{\"app_secret\": \"your_actual_app_secret\"}'")
    print(")")
    
    # Show what the combined request would look like
    client = SchwabClient()
    validation = client.validate_request_args(
        "example_requests/base_credentials.json",
        '{"app_key": "your_actual_app_key"}',
        '{"app_secret": "your_actual_app_secret"}'
    )
    
    print("\n3. Combined request would be:")
    if validation['success']:
        print_response(validation['request'], "Final Request")
    else:
        print_response(validation, "Validation Error")

def demonstrate_interactive_mode():
    """Interactive demonstration."""
    print_section("Interactive File Request Mode")
    
    client = SchwabClient()
    
    try:
        if not client.connect():
            print("Failed to connect to server. Make sure the server is running.")
            return
        
        print("Enter file-based requests. Examples:")
        print("  ping.json")
        print("  base_symbol.json {\"symbol\": \"AAPL\"}")
        print("  base_creds.json {\"app_key\": \"key\"} {\"app_secret\": \"secret\"}")
        print("Type 'quit' to exit.")
        
        while True:
            print("\n" + "-"*40)
            user_input = input("Enter request: ").strip()
            
            if user_input.lower() == 'quit':
                break
            elif not user_input:
                continue
            
            # Parse the input into arguments
            args = []
            current_arg = ""
            in_json = False
            brace_count = 0
            
            for char in user_input:
                if char == '{':
                    in_json = True
                    brace_count += 1
                    current_arg += char
                elif char == '}':
                    brace_count -= 1
                    current_arg += char
                    if brace_count == 0:
                        in_json = False
                elif char == ' ' and not in_json:
                    if current_arg.strip():
                        args.append(current_arg.strip())
                        current_arg = ""
                else:
                    current_arg += char
            
            if current_arg.strip():
                args.append(current_arg.strip())
            
            if not args:
                continue
            
            # Add example_requests/ prefix if it's just a filename
            processed_args = []
            for arg in args:
                if ':' not in arg and not arg.startswith('{') and not arg.endswith('.json'):
                    processed_args.append(f"example_requests/{arg}.json")
                elif ':' not in arg and not arg.startswith('{') and not os.path.exists(arg):
                    processed_args.append(f"example_requests/{arg}")
                else:
                    processed_args.append(arg)
            
            # Validate first
            validation = client.validate_request_args(*processed_args)
            if not validation['success']:
                print("❌ Invalid request:")
                print_response(validation)
                continue
            
            # Send request
            print("✅ Valid request. Sending to server...")
            response = client.send_request(*processed_args)
            print_response(response, "Server Response")
    
    except KeyboardInterrupt:
        print("\nInteractive session interrupted.")
    except Exception as e:
        print(f"Error during interactive session: {str(e)}")
    finally:
        client.disconnect()

def create_example_files():
    """Create example files if they don't exist."""
    os.makedirs("example_requests", exist_ok=True)
    
    examples = {
        "ping.json": {"action": "ping"},
        "test_connection.json": {"action": "test_connection"},
        "get_accounts.json": {"action": "get_linked_accounts"},
        "get_positions.json": {"action": "get_positions"},
        "base_symbol_request.json": {"action": "get_positions_by_symbol"},
        "base_credentials.json": {
            "action": "initialize_credentials",
            "callback_url": "https://127.0.0.1",
            "tokens_file": "tokens.json"
        },
        "account_details.json": {
            "action": "get_account_details",
            "include_positions": False
        }
    }
    
    for filename, content in examples.items():
        filepath = f"example_requests/{filename}"
        with open(filepath, 'w') as f:
            json.dump(content, f, indent=2)
        print(f"Created: {filepath}")

def main():
    """Main demonstration function."""
    print("Schwab API Client - File-Based Arguments Demo")
    
    # Ensure example files exist
    if not os.path.exists("example_requests"):
        print("Creating example request files...")
        create_example_files()
    
    # Run demonstrations
    demonstrate_file_loading()
    demonstrate_argument_combinations()
    demonstrate_credential_setup()
    demonstrate_real_usage()
    
    # Ask if user wants interactive mode
    print("\n" + "="*60)
    interactive = input("Would you like to try interactive file mode? (y/n): ").lower().strip()
    if interactive == 'y':
        demonstrate_interactive_mode()
    
    print("\n" + "="*60)
    print("File-Based Client Demo Complete!")
    print("\nKey Features Demonstrated:")
    print("✓ Loading JSON requests from files")
    print("✓ Combining files with JSON strings")
    print("✓ Multiple argument combinations")
    print("✓ File + dictionary + JSON mixing")
    print("✓ Validation before sending")
    print("✓ Interactive file-based requests")
    
    print("\nUsage Patterns:")
    print("client.send_request('request.json')")
    print("client.send_request('base.json', '{\"override\": \"value\"}')")
    print("client.send_request(dict, 'file.json', '{\"more\": \"data\"}')")
    print("client.send_from_file('file.json', additional_args...)")

if __name__ == "__main__":
    main()