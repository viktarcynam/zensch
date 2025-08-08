#!/usr/bin/env python3
"""
Startup script for the Schwab API server without requiring credentials upfront.
The server will start and accept credentials via the 'initialize_credentials' action.
"""
import sys
from server import SchwabServer
from config import config

def main():
    """Main startup function."""
    try:
        print("Starting Schwab API Server (No Credentials Mode)")
        print("=" * 50)
        print(f"Server will run on {config.server_host}:{config.server_port}")
        print()
        print("The server will start without credentials.")
        print("You can initialize credentials later using one of these methods:")
        print()
        print("1. Using the client:")
        print("   client.initialize_credentials(app_key, app_secret)")
        print()
        print("2. Using JSON string:")
        print('   client.send_request(\'{"action": "initialize_credentials", "app_key": "...", "app_secret": "..."}\')')
        print()
        print("3. Using file + JSON:")
        print('   client.send_request("base_credentials.json", \'{"app_key": "...", "app_secret": "..."}\')')
        print()
        
        # Ask for confirmation
        confirm = input("Start server without credentials? (y/n): ").lower().strip()
        if confirm != 'y':
            print("Server startup cancelled.")
            sys.exit(0)
        
        # Create server
        server = SchwabServer()
        
        print("\nServer starting...")
        print(f"Server is now running on {config.server_host}:{config.server_port}")
        print("Server is ready to accept connections.")
        print("Use 'initialize_credentials' action to set up API access.")
        print("Press Ctrl+C to stop the server.")
        
        # Start the server (without initializing services)
        server.start()
        
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()