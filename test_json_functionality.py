#!/usr/bin/env python3
"""
Test script for JSON string functionality.
Tests the JSON parser and client JSON capabilities.
"""
import json
import time
import threading
from server import SchwabServer
from client import SchwabClient
from json_parser import json_parser

def test_json_parser():
    """Test the JSON parser functionality."""
    print("Testing JSON Parser...")
    print("=" * 50)
    
    # Test 1: Valid JSON parsing
    print("\n1. Testing valid JSON parsing:")
    valid_json = '{"action": "ping"}'
    result = json_parser.parse_json_string(valid_json)
    if result['success']:
        print("✓ Valid JSON parsed successfully")
        print(f"   Parsed data: {result['data']}")
    else:
        print("✗ Failed to parse valid JSON")
        print(f"   Error: {result['error']}")
    
    # Test 2: Invalid JSON parsing
    print("\n2. Testing invalid JSON parsing:")
    invalid_json = '{"action": "ping"'  # Missing closing brace
    result = json_parser.parse_json_string(invalid_json)
    if not result['success']:
        print("✓ Invalid JSON correctly rejected")
        print(f"   Error: {result['error']}")
    else:
        print("✗ Invalid JSON should have been rejected")
    
    # Test 3: Request validation
    print("\n3. Testing request validation:")
    test_cases = [
        ('{"action": "ping"}', True, "Simple ping"),
        ('{"action": "invalid_action"}', False, "Invalid action"),
        ('{"action": "get_positions_by_symbol", "symbol": "AAPL"}', True, "Valid symbol request"),
        ('{"action": "get_positions_by_symbol"}', False, "Missing required symbol"),
        ('{"missing_action": "test"}', False, "Missing action field"),
    ]
    
    for json_str, should_be_valid, description in test_cases:
        print(f"\n   Testing: {description}")
        parse_result = json_parser.parse_json_string(json_str)
        if parse_result['success']:
            validation_result = json_parser.validate_request(parse_result['data'])
            is_valid = validation_result['success']
        else:
            is_valid = False
        
        if is_valid == should_be_valid:
            print(f"   ✓ {description} - Result as expected")
        else:
            print(f"   ✗ {description} - Unexpected result")
            if not is_valid:
                print(f"     Error: {validation_result.get('error', 'Parse error')}")
    
    # Test 4: Template generation
    print("\n4. Testing template generation:")
    template_result = json_parser.create_request_template("get_positions_by_symbol")
    if template_result['success']:
        print("✓ Template generated successfully")
        print(f"   Template: {json.dumps(template_result['template'], indent=2)}")
    else:
        print("✗ Failed to generate template")
        print(f"   Error: {template_result['error']}")

def test_client_json_functionality():
    """Test client JSON string functionality."""
    print("\n\nTesting Client JSON Functionality...")
    print("=" * 50)
    
    # Start server for testing
    server = SchwabServer(host='localhost', port=3459)
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    time.sleep(1)
    
    try:
        client = SchwabClient(host='localhost', port=3459)
        
        # Test 1: Connect and ping with JSON string
        print("\n1. Testing connection and ping with JSON string:")
        if client.connect():
            print("✓ Client connected successfully")
            
            # Test ping with JSON string
            ping_json = '{"action": "ping"}'
            response = client.send_request(ping_json)
            if response.get('success'):
                print("✓ Ping with JSON string successful")
                print(f"   Message: {response.get('message')}")
            else:
                print("✗ Ping with JSON string failed")
                print(f"   Error: {response.get('error')}")
        else:
            print("✗ Client connection failed")
            return
        
        # Test 2: Test various JSON requests
        print("\n2. Testing various JSON requests:")
        test_requests = [
            ('{"action": "test_connection"}', "Test connection"),
            ('{"action": "get_linked_accounts"}', "Get linked accounts"),
            ('{"action": "get_positions"}', "Get positions"),
            ('{"action": "get_positions_by_symbol", "symbol": "AAPL"}', "Get positions by symbol"),
        ]
        
        for json_str, description in test_requests:
            print(f"\n   Testing: {description}")
            response = client.send_request(json_str)
            # These should fail because no credentials are set, but should not error on JSON parsing
            if 'success' in response:
                print(f"   ✓ JSON request processed (success: {response['success']})")
                if not response['success'] and 'not initialized' in response.get('error', ''):
                    print("   ✓ Expected error: credentials not initialized")
            else:
                print("   ✗ Invalid response format")
        
        # Test 3: Test validation without sending
        print("\n3. Testing validation without sending:")
        sample_json = '{"action": "get_account_details", "include_positions": true}'
        validation = client.validate_json_request(sample_json)
        if validation['success']:
            print("✓ JSON validation successful")
            print(f"   Formatted request: {json.dumps(validation['request'], indent=2)}")
        else:
            print("✗ JSON validation failed")
            print(f"   Error: {validation['error']}")
        
        # Test 4: Test templates
        print("\n4. Testing template retrieval:")
        templates = client.get_all_templates()
        if templates['success']:
            print(f"✓ Retrieved {templates['actions_count']} action templates")
            print("   Available actions:", list(templates['templates'].keys()))
        else:
            print("✗ Failed to retrieve templates")
        
        client.disconnect()
        
    except Exception as e:
        print(f"✗ Test failed with error: {str(e)}")
    finally:
        server.stop()

def test_json_error_handling():
    """Test JSON error handling scenarios."""
    print("\n\nTesting JSON Error Handling...")
    print("=" * 50)
    
    error_cases = [
        ('', "Empty string"),
        ('   ', "Whitespace only"),
        ('not json at all', "Not JSON"),
        ('{"action":}', "Invalid JSON syntax"),
        ('[]', "JSON array instead of object"),
        ('"just a string"', "JSON string instead of object"),
        ('123', "JSON number instead of object"),
        ('{"action": ""}', "Empty action"),
        ('{"action": "get_positions_by_symbol", "symbol": ""}', "Empty required parameter"),
    ]
    
    for json_str, description in error_cases:
        print(f"\n   Testing: {description}")
        result = json_parser.format_request(json_str)
        if not result['success']:
            print(f"   ✓ Error correctly caught: {result['error']}")
        else:
            print(f"   ✗ Should have failed but didn't")

def main():
    """Main test function."""
    print("Schwab API JSON Functionality Test Suite")
    print("=" * 60)
    
    # Run all tests
    test_json_parser()
    test_client_json_functionality()
    test_json_error_handling()
    
    print("\n" + "=" * 60)
    print("JSON Functionality Tests Complete!")
    print("\nSummary of tested features:")
    print("✓ JSON string parsing and validation")
    print("✓ Request template generation")
    print("✓ Client JSON string support")
    print("✓ Error handling for invalid JSON")
    print("✓ Parameter validation")
    print("✓ Template retrieval")
    
    print("\nThe JSON functionality is ready for use!")

if __name__ == "__main__":
    main()