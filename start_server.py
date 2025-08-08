#!/usr/bin/env python3
"""
Startup script for the Schwab API server.
Provides an interactive way to start the server with credentials.
"""
import sys
import os
import getpass
from server import SchwabServer
from config import config

def get_credentials():
    """Get credentials from user input."""
    print("Schwab API Server Startup")
    print("=" * 40)
    
    # Check if credentials are already configured
    if config.is_configured():
        print("Credentials found in environment variables.")
        use_env = input("Use existing credentials? (y/n): ").lower().strip()
        if use_env == 'y':
            return config.app_key, config.app_secret, config.callback_url, config.tokens_file
    
    print("\nPlease provide your Schwab API credentials:")
    print("(You can get these from https://developer.schwab.com/)")
    
    app_key = input("App Key: ").strip()
    if not app_key:
        print("App Key is required!")
        return None, None, None, None
    
    app_secret = getpass.getpass("App Secret: ").strip()
    if not app_secret:
        print("App Secret is required!")
        return None, None, None, None
    
    callback_url = input(f"Callback URL (default: {config.callback_url}): ").strip()
    if not callback_url:
        callback_url = config.callback_url
    
    tokens_file = input(f"Tokens file (default: {config.tokens_file}): ").strip()
    if not tokens_file:
        tokens_file = config.tokens_file
    
    return app_key, app_secret, callback_url, tokens_file

def main():
    """Main startup function."""
    try:
        print("Schwab API Server Startup Options")
        print("=" * 40)
        print(f"Server will run on {config.server_host}:{config.server_port}")
        print()
        print("Choose startup mode:")
        print("1. Start with credentials (traditional)")
        print("2. Start without credentials (initialize later)")
        print("3. Auto-detect from environment")
        print()
        
        choice = input("Enter choice (1-3): ").strip()
        
        if choice == "1":
            # Traditional mode - require credentials upfront
            print("\n--- Starting with Credentials ---")
            app_key, app_secret, callback_url, tokens_file = get_credentials()
            
            if not app_key or not app_secret:
                print("Cannot start server without valid credentials.")
                sys.exit(1)
            
            # Create and configure server
            server = SchwabServer()
            
            print("\nInitializing Schwab API services...")
            server.initialize_services(app_key, app_secret, callback_url, tokens_file)
            
            print("Server initialized successfully!")
            print(f"Server is now running on {config.server_host}:{config.server_port}")
            print("Press Ctrl+C to stop the server.")
            print("\nYou can now use the client to connect and make requests.")
            
        elif choice == "2":
            # No credentials mode
            print("\n--- Starting without Credentials ---")
            print("The server will start without credentials.")
            print("You can initialize credentials later using:")
            print("  client.initialize_credentials(app_key, app_secret)")
            print('  client.send_request(\'{"action": "initialize_credentials", ...}\')')
            print()
            
            confirm = input("Continue? (y/n): ").lower().strip()
            if confirm != 'y':
                print("Server startup cancelled.")
                sys.exit(0)
            
            server = SchwabServer()
            print(f"Server is now running on {config.server_host}:{config.server_port}")
            print("Server is ready to accept connections.")
            print("Use 'initialize_credentials' action to set up API access.")
            print("Press Ctrl+C to stop the server.")
            
        elif choice == "3":
            # Auto-detect mode
            print("\n--- Auto-detecting Configuration ---")
            server = SchwabServer()
            
            if config.is_configured():
                print("Credentials found in environment variables.")
                print("Initializing server with configured credentials...")
                server.initialize_services(config.app_key, config.app_secret)
                print("Server initialized successfully!")
                
            elif config.can_start_with_tokens():
                print("Valid tokens and stored credentials found.")
                print("Initializing server with stored credentials...")
                try:
                    app_key, app_secret, callback_url = config.get_stored_credentials()
                    if app_key and app_secret:
                        server.initialize_services(app_key, app_secret, callback_url)
                        print("Server initialized successfully with stored credentials!")
                    else:
                        raise Exception("Could not retrieve stored credentials")
                except Exception as e:
                    print(f"Failed to initialize with stored credentials: {e}")
                    print("Server starting without credentials.")
                    print("Use 'initialize_credentials' action to set up API access.")
                    
            else:
                print("No credentials or valid tokens found.")
                print("Server starting without credentials.")
                print("Use 'initialize_credentials' action to set up API access.")
            
            print(f"Server is now running on {config.server_host}:{config.server_port}")
            print("Press Ctrl+C to stop the server.")
            
        else:
            print("Invalid choice. Exiting.")
            sys.exit(1)
        
        # Start the server
        server.start()
        
    except KeyboardInterrupt:
        print("\nServer stopped by user.")
    except Exception as e:
        print(f"Error starting server: {str(e)}")
        sys.exit(1)

if __name__ == "__main__":
    main()