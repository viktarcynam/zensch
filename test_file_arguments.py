#!/usr/bin/env python3
"""
Test script for file-based argument functionality.
Tests loading JSON from files and combining with additional arguments.
"""
import json
import time
import threading
import os
from server import SchwabServer
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

def test_json_file_loading():
    """Test loading JSON from files."""
    print_section("Testing JSON File Loading")
    
    # Test loading existing files
    test_files = [
        "example_requests/ping.json",
        "example_requests/get_positions.json",
        "example_requests/base_credentials.json",
        "example_requests/account_details.json"
    ]
    
    for filename in test_files:
        print(f"\nTesting file: {filename}")
        result = json_parser.load_json_file(filename)
        if result['success']:
            print("✓ File loaded successfully")
            print(f"   Content: {json.dumps(result['data'], indent=2)}")
        else:
            print("✗ Failed to load file")
            print(f"   Error: {result['error']}")
    
    # Test loading non-existent file
    print(f"\nTesting non-existent file:")
    result = json_parser.load_json_file("nonexistent.json")
    if not result['success']:
        print("✓ Non-existent file correctly rejected")
        print(f"   Error: {result['error']}")
    else:
        print("✗ Should have failed for non-existent file")

def test_argument_parsing():
    """Test parsing different types of arguments."""
    print_section("Testing Argument Parsing")
    
    # Test 1: Single filename
    print("\n1. Testing single filename:")
    result = json_parser.parse_arguments("example_requests/ping.json")
    if result['success']:
        print("✓ Single filename parsed successfully")
        print(f"   Data: {json.dumps(result['data'], indent=2)}")
        print(f"   Processed: {result['processed_args']}")
    else:
        print("✗ Failed to parse single filename")
        print(f"   Error: {result['error']}")
    
    # Test 2: Single JSON string
    print("\n2. Testing single JSON string:")
    result = json_parser.parse_arguments('{"action": "test_connection"}')
    if result['success']:
        print("✓ Single JSON string parsed successfully")
        print(f"   Data: {json.dumps(result['data'], indent=2)}")
        print(f"   Processed: {result['processed_args']}")
    else:
        print("✗ Failed to parse single JSON string")
        print(f"   Error: {result['error']}")
    
    # Test 3: Filename + JSON string (combining)
    print("\n3. Testing filename + JSON string combination:")
    result = json_parser.parse_arguments(
        "example_requests/base_symbol_request.json",
        '{"symbol": "AAPL"}'
    )
    if result['success']:
        print("✓ File + JSON combination successful")
        print(f"   Combined data: {json.dumps(result['data'], indent=2)}")
        print(f"   Processed: {result['processed_args']}")
    else:
        print("✗ Failed to combine file + JSON")
        print(f"   Error: {result['error']}")
    
    # Test 4: Multiple files + JSON
    print("\n4. Testing multiple files + JSON:")
    result = json_parser.parse_arguments(
        "example_requests/base_credentials.json",
        '{"app_key": "test_key"}',
        '{"app_secret": "test_secret"}'
    )
    if result['success']:
        print("✓ Multiple arguments combined successfully")
        print(f"   Combined data: {json.dumps(result['data'], indent=2)}")
        print(f"   Processed: {result['processed_args']}")
    else:
        print("✗ Failed to combine multiple arguments")
        print(f"   Error: {result['error']}")
    
    # Test 5: Dictionary argument
    print("\n5. Testing dictionary argument:")
    result = json_parser.parse_arguments(
        {"action": "get_positions"},
        '{"account_hash": "ABC123"}'
    )
    if result['success']:
        print("✓ Dictionary + JSON combination successful")
        print(f"   Combined data: {json.dumps(result['data'], indent=2)}")
        print(f"   Processed: {result['processed_args']}")
    else:
        print("✗ Failed to combine dictionary + JSON")
        print(f"   Error: {result['error']}")

def test_request_formatting():
    """Test formatting requests from arguments."""
    print_section("Testing Request Formatting from Arguments")
    
    test_cases = [
        # (description, args)
        ("Simple file", ("example_requests/ping.json",)),
        ("File + JSON override", ("example_requests/base_symbol_request.json", '{"symbol": "TSLA"}')),
        ("Credentials from file + keys", ("example_requests/base_credentials.json", '{"app_key": "key123", "app_secret": "secret456"}')),
        ("Account details with override", ("example_requests/account_details.json", '{"include_positions": true}')),
    ]
    
    for description, args in test_cases:
        print(f"\n{description}:")
        result = json_parser.format_request_from_args(*args)
        if result['success']:
            print("✓ Request formatted successfully")
            print(f"   Request: {json.dumps(result['request'], indent=2)}")
            print(f"   Processed: {result['processed_args']}")
        else:
            print("✗ Failed to format request")
            print(f"   Error: {result['error']}")

def test_client_file_functionality():
    """Test client functionality with files."""
    print_section("Testing Client File Functionality")
    
    # Start server for testing
    server = SchwabServer(host='localhost', port=3460)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(1)
    
    try:
        client = SchwabClient(host='localhost', port=3460)
        
        if not client.connect():
            print("Failed to connect to server")
            return
        
        # Test 1: Send request from file
        print("\n1. Testing send request from file:")
        response = client.send_request("example_requests/ping.json")
        if response.get('success'):
            print("✓ File request successful")
            print(f"   Message: {response.get('message')}")
        else:
            print("✗ File request failed")
            print(f"   Error: {response.get('error')}")
        
        # Test 2: Send request from file + JSON combination
        print("\n2. Testing file + JSON combination:")
        response = client.send_request(
            "example_requests/base_symbol_request.json",
            '{"symbol": "AAPL"}'
        )
        if 'success' in response:
            print(f"✓ Combined request processed (success: {response['success']})")
            if not response['success'] and 'not initialized' in response.get('error', ''):
                print("   ✓ Expected error: credentials not initialized")
        else:
            print("✗ Invalid response format")
        
        # Test 3: Validate file arguments without sending
        print("\n3. Testing validation without sending:")
        validation = client.validate_request_args(
            "example_requests/base_credentials.json",
            '{"app_key": "test_key", "app_secret": "test_secret"}'
        )
        if validation['success']:
            print("✓ File arguments validation successful")
            print(f"   Request: {json.dumps(validation['request'], indent=2)}")
        else:
            print("✗ File arguments validation failed")
            print(f"   Error: {validation['error']}")
        
        # Test 4: Load JSON file directly
        print("\n4. Testing direct file loading:")
        file_result = client.load_json_file("example_requests/account_details.json")
        if file_result['success']:
            print("✓ File loaded successfully")
            print(f"   Data: {json.dumps(file_result['data'], indent=2)}")
        else:
            print("✗ File loading failed")
            print(f"   Error: {file_result['error']}")
        
        # Test 5: Send from file with additional args
        print("\n5. Testing send_from_file method:")
        response = client.send_from_file(
            "example_requests/account_details.json",
            '{"include_positions": true}'
        )
        if 'success' in response:
            print(f"✓ send_from_file processed (success: {response['success']})")
            if not response['success']:
                print(f"   Expected error: {response.get('error')}")
        else:
            print("✗ send_from_file failed")
        
        client.disconnect()
        
    except Exception as e:
        print(f"✗ Test failed with error: {str(e)}")
    finally:
        server.stop()

def test_error_handling():
    """Test error handling for file operations."""
    print_section("Testing Error Handling")
    
    error_cases = [
        ("Non-existent file", ("nonexistent.json",)),
        ("Empty filename", ("",)),
        ("Invalid JSON in args", ("example_requests/ping.json", "invalid json")),
        ("File + invalid action", ("example_requests/ping.json", '{"action": "invalid"}')),
    ]
    
    for description, args in error_cases:
        print(f"\n{description}:")
        result = json_parser.format_request_from_args(*args)
        if not result['success']:
            print(f"✓ Error correctly caught: {result['error']}")
        else:
            print(f"✗ Should have failed but didn't")

def main():
    """Main test function."""
    print("Schwab API File Arguments Test Suite")
    print("=" * 60)
    
    # Check if example files exist
    if not os.path.exists("example_requests"):
        print("Error: example_requests directory not found!")
        print("Make sure the example JSON files are created.")
        return
    
    # Run all tests
    test_json_file_loading()
    test_argument_parsing()
    test_request_formatting()
    test_client_file_functionality()
    test_error_handling()
    
    print("\n" + "=" * 60)
    print("File Arguments Tests Complete!")
    print("\nSummary of tested features:")
    print("✓ JSON file loading and parsing")
    print("✓ Argument parsing (files, JSON strings, dictionaries)")
    print("✓ Request combination and formatting")
    print("✓ Client file-based requests")
    print("✓ Error handling for file operations")
    print("✓ Validation without sending")
    
    print("\nUsage examples:")
    print("client.send_request('ping.json')")
    print("client.send_request('base.json', '{\"key\": \"value\"}')")
    print("client.send_from_file('request.json', additional_json)")

if __name__ == "__main__":
    main()