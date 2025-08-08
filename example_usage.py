"""
Example usage of the Schwab API client-server system.
This script demonstrates how to use the client to communicate with the server.
"""
import json
import time
from client import SchwabClient

def print_response(title: str, response: dict):
    """Helper function to print formatted responses."""
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"{'='*50}")
    print(json.dumps(response, indent=2))

def main():
    """Main example function."""
    print("Schwab API Client-Server Example")
    print("Make sure the server is running before executing this script!")
    
    # Create client instance
    client = SchwabClient()
    
    try:
        # Connect to server
        if not client.connect():
            print("Failed to connect to server. Make sure the server is running.")
            return
        
        # 1. Ping the server
        print_response("1. Ping Server", client.ping())
        
        # 2. Test connection (will fail if credentials not initialized)
        print_response("2. Test Connection", client.test_connection())
        
        # 3. Initialize credentials (replace with your actual credentials)
        print("\n" + "="*50)
        print("3. Initialize Credentials")
        print("="*50)
        print("Please provide your Schwab API credentials:")
        
        app_key = input("Enter your App Key: ").strip()
        app_secret = input("Enter your App Secret: ").strip()
        
        if app_key and app_secret:
            response = client.initialize_credentials(app_key, app_secret)
            print(json.dumps(response, indent=2))
            
            if response.get('success'):
                print("\nCredentials initialized successfully!")
                
                # Wait a moment for authentication to complete
                print("Waiting for authentication to complete...")
                time.sleep(2)
                
                # 4. Test connection again
                print_response("4. Test Connection (After Auth)", client.test_connection())
                
                # 5. Get linked accounts
                print_response("5. Get Linked Accounts", client.get_linked_accounts())
                
                # 6. Get account summary
                print_response("6. Get Account Summary", client.get_account_summary())
                
                # 7. Get positions
                print_response("7. Get All Positions", client.get_positions())
                
                # 8. Get positions for a specific symbol (example with AAPL)
                symbol = input("\nEnter a symbol to search for positions (e.g., AAPL): ").strip().upper()
                if symbol:
                    print_response(f"8. Get Positions for {symbol}", 
                                 client.get_positions_by_symbol(symbol))
                
                # 9. Get account details with positions
                print_response("9. Get Account Details with Positions", 
                             client.get_account_details(include_positions=True))
                
            else:
                print("Failed to initialize credentials. Please check your app key and secret.")
        else:
            print("Skipping credential initialization - no credentials provided.")
    
    except KeyboardInterrupt:
        print("\nExample interrupted by user.")
    except Exception as e:
        print(f"\nError during example execution: {str(e)}")
    finally:
        # Disconnect from server
        client.disconnect()
        print("\nExample completed.")

if __name__ == "__main__":
    main()