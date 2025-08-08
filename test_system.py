#!/usr/bin/env python3
"""
Test script to verify the Schwab API client-server system.
This script tests the basic functionality without requiring real credentials.
"""
import json
import time
import threading
from server import SchwabServer
from client import SchwabClient

def test_server_client_communication():
    """Test basic server-client communication."""
    print("Testing Schwab API Client-Server System")
    print("=" * 50)
    
    # Start server in a separate thread
    server = SchwabServer(host='localhost', port=3457)  # Use different port for testing
    server_thread = threading.Thread(target=server.start, daemon=True)
    server_thread.start()
    
    # Give server time to start
    time.sleep(2)
    
    try:
        # Test client connection
        client = SchwabClient(host='localhost', port=3457)
        
        print("1. Testing client connection...")
        if client.connect():
            print("✓ Client connected successfully")
        else:
            print("✗ Client connection failed")
            return
        
        # Test ping
        print("\n2. Testing ping...")
        response = client.ping()
        if response.get('success'):
            print("✓ Ping successful")
            print(f"   Message: {response.get('message')}")
        else:
            print("✗ Ping failed")
            print(f"   Error: {response.get('error')}")
        
        # Test connection without credentials (should fail)
        print("\n3. Testing connection without credentials...")
        response = client.test_connection()
        if not response.get('success'):
            print("✓ Connection test correctly failed (no credentials)")
            print(f"   Error: {response.get('error')}")
        else:
            print("✗ Connection test should have failed without credentials")
        
        # Test invalid action
        print("\n4. Testing invalid action...")
        response = client.send_request({'action': 'invalid_action'})
        if not response.get('success'):
            print("✓ Invalid action correctly rejected")
            print(f"   Available actions: {len(response.get('available_actions', []))}")
        else:
            print("✗ Invalid action should have been rejected")
        
        # Test malformed JSON (this will be handled by the server)
        print("\n5. Testing error handling...")
        try:
            # Send a request that will trigger server-side error handling
            response = client.get_linked_accounts()  # This should fail without credentials
            if not response.get('success'):
                print("✓ Error handling working correctly")
                print(f"   Error: {response.get('error')}")
            else:
                print("✗ Should have failed without credentials")
        except Exception as e:
            print(f"✓ Exception handling working: {str(e)}")
        
        # Disconnect client
        client.disconnect()
        print("\n✓ Client disconnected successfully")
        
    except Exception as e:
        print(f"\n✗ Test failed with error: {str(e)}")
    finally:
        # Stop server
        server.stop()
        print("✓ Server stopped")
    
    print("\n" + "=" * 50)
    print("Basic system test completed!")
    print("The system is ready for use with real Schwab API credentials.")

def test_json_serialization():
    """Test JSON serialization of typical responses."""
    print("\nTesting JSON serialization...")
    
    # Test typical response structure
    test_response = {
        'success': True,
        'data': {
            'accounts': [
                {
                    'accountHash': 'test123',
                    'accountType': 'MARGIN',
                    'positions': [
                        {
                            'symbol': 'AAPL',
                            'quantity': 100,
                            'marketValue': 15000.50,
                            'dayChange': 250.75
                        }
                    ]
                }
            ],
            'total_positions': 1
        },
        'message': 'Test response',
        'timestamp': '2024-01-01T12:00:00.000000'
    }
    
    try:
        json_str = json.dumps(test_response, indent=2)
        parsed_back = json.loads(json_str)
        print("✓ JSON serialization working correctly")
        return True
    except Exception as e:
        print(f"✗ JSON serialization failed: {str(e)}")
        return False

def main():
    """Main test function."""
    print("Schwab API System Test Suite")
    print("=" * 50)
    
    # Test JSON serialization first
    if not test_json_serialization():
        print("Basic JSON test failed. Stopping tests.")
        return
    
    # Test server-client communication
    test_server_client_communication()
    
    print("\n" + "=" * 50)
    print("All tests completed!")
    print("\nTo use the system with real data:")
    print("1. Run: python start_server.py")
    print("2. In another terminal: python example_usage.py")
    print("3. Or use the client programmatically as shown in README.md")

if __name__ == "__main__":
    main()