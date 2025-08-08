"""
TCP Server for Schwab API services.
Runs in the background and handles client requests for account and position data.
"""
import socket
import threading
import json
import logging
from typing import Dict, Any
import signal
import sys
from datetime import datetime

from config import config
from schwab_auth import SchwabAuthenticator
from account_service import AccountService
from positions_service import PositionsService

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler('schwab_server.log'),
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

class SchwabServer:
    """TCP Server for handling Schwab API requests."""
    
    def __init__(self, host: str = None, port: int = None):
        """
        Initialize the Schwab server.
        
        Args:
            host: Server host address
            port: Server port number
        """
        self.host = host or config.server_host
        self.port = port or config.server_port
        self.socket = None
        self.running = False
        self.authenticator = None
        self.account_service = None
        self.positions_service = None
        
        # Setup signal handlers for graceful shutdown
        signal.signal(signal.SIGINT, self._signal_handler)
        signal.signal(signal.SIGTERM, self._signal_handler)
    
    def initialize_services(self, app_key: str, app_secret: str, 
                          callback_url: str = None, tokens_file: str = None):
        """
        Initialize Schwab API services with credentials.
        
        Args:
            app_key: Schwab API app key
            app_secret: Schwab API app secret
            callback_url: OAuth callback URL
            tokens_file: Path to tokens file
        """
        try:
            logger.info("Initializing Schwab API services...")
            
            self.authenticator = SchwabAuthenticator(
                app_key=app_key,
                app_secret=app_secret,
                callback_url=callback_url,
                tokens_file=tokens_file
            )
            
            # Test authentication
            if not self.authenticator.test_connection():
                raise Exception("Failed to authenticate with Schwab API")
            
            self.account_service = AccountService(self.authenticator)
            self.positions_service = PositionsService(self.authenticator)
            
            logger.info("Schwab API services initialized successfully")
            
        except Exception as e:
            logger.error(f"Failed to initialize services: {str(e)}")
            raise
    

    def start(self):
        """Start the TCP server."""
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.socket.bind((self.host, self.port))
            self.socket.listen(5)
            
            self.running = True
            logger.info(f"Schwab server started on {self.host}:{self.port}")
            
            while self.running:
                try:
                    client_socket, address = self.socket.accept()
                    logger.info(f"New client connected from {address}")
                    
                    # Handle client in a separate thread
                    client_thread = threading.Thread(
                        target=self._handle_client,
                        args=(client_socket, address)
                    )
                    client_thread.daemon = True
                    client_thread.start()
                    
                except socket.error as e:
                    if self.running:
                        logger.error(f"Socket error: {str(e)}")
                    break
                    
        except Exception as e:
            logger.error(f"Server error: {str(e)}")
        finally:
            self.stop()
    
    def stop(self):
        """Stop the TCP server."""
        logger.info("Stopping Schwab server...")
        self.running = False
        
        if self.socket:
            try:
                self.socket.close()
            except:
                pass
        
        logger.info("Schwab server stopped")
    
    def _signal_handler(self, signum, frame):
        """Handle shutdown signals."""
        logger.info(f"Received signal {signum}, shutting down...")
        self.stop()
        sys.exit(0)
    
    def _handle_client(self, client_socket: socket.socket, address: tuple):
        """
        Handle individual client connections.
        
        Args:
            client_socket: Client socket connection
            address: Client address tuple
        """
        try:
            while self.running:
                # Receive data from client
                data = client_socket.recv(4096)
                if not data:
                    break
                
                try:
                    # Parse JSON request
                    request = json.loads(data.decode('utf-8'))
                    logger.info(f"Received request from {address}: {request.get('action', 'unknown')}")
                    
                    # Process request
                    response = self._process_request(request)
                    
                    # Send response
                    response_json = json.dumps(response, indent=2)
                    client_socket.send(response_json.encode('utf-8'))
                    
                except json.JSONDecodeError as e:
                    error_response = {
                        'success': False,
                        'error': f'Invalid JSON format: {str(e)}',
                        'timestamp': datetime.now().isoformat()
                    }
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                    
                except Exception as e:
                    logger.error(f"Error processing request from {address}: {str(e)}")
                    error_response = {
                        'success': False,
                        'error': f'Server error: {str(e)}',
                        'timestamp': datetime.now().isoformat()
                    }
                    client_socket.send(json.dumps(error_response).encode('utf-8'))
                    
        except Exception as e:
            logger.error(f"Client handler error for {address}: {str(e)}")
        finally:
            try:
                client_socket.close()
                logger.info(f"Client {address} disconnected")
            except:
                pass
    
    def _process_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process client requests and return appropriate responses.
        
        Args:
            request: Client request dictionary
            
        Returns:
            Dict containing response data
        """
        try:
            action = request.get('action', '').lower()
            timestamp = datetime.now().isoformat()
            
            # Handle actions that don't require authentication first
            if action == 'ping':
                return {
                    'success': True,
                    'message': 'Server is running',
                    'timestamp': timestamp
                }
            
            elif action == 'initialize_credentials':
                app_key = request.get('app_key')
                app_secret = request.get('app_secret')
                callback_url = request.get('callback_url')
                tokens_file = request.get('tokens_file')
                
                if not app_key or not app_secret:
                    return {
                        'success': False,
                        'error': 'app_key and app_secret are required',
                        'timestamp': timestamp
                    }
                
                try:
                    self.initialize_services(app_key, app_secret, callback_url, tokens_file)
                    return {
                        'success': True,
                        'message': 'Credentials initialized successfully',
                        'timestamp': timestamp
                    }
                except Exception as e:
                    return {
                        'success': False,
                        'error': f'Failed to initialize credentials: {str(e)}',
                        'timestamp': timestamp
                    }
            
            # Check if services are initialized for other actions
            if not self.authenticator or not self.account_service or not self.positions_service:
                return {
                    'success': False,
                    'error': 'Server services not initialized. Please provide credentials.',
                    'timestamp': timestamp
                }
            
            # Handle authenticated actions
            if action == 'test_connection':
                is_connected = self.authenticator.test_connection()
                return {
                    'success': is_connected,
                    'message': 'Connection test successful' if is_connected else 'Connection test failed',
                    'timestamp': timestamp
                }
            
            elif action == 'get_linked_accounts':
                result = self.account_service.get_linked_accounts()
                result['timestamp'] = timestamp
                return result
            
            elif action == 'get_account_details':
                account_hash = request.get('account_hash')
                include_positions = request.get('include_positions', False)
                
                if account_hash:
                    result = self.account_service.get_account_details(account_hash, include_positions)
                else:
                    result = self.account_service.get_all_account_details(include_positions)
                
                result['timestamp'] = timestamp
                return result
            
            elif action == 'get_account_summary':
                account_hash = request.get('account_hash')
                result = self.account_service.get_account_summary(account_hash)
                result['timestamp'] = timestamp
                return result
            
            elif action == 'get_positions':
                account_hash = request.get('account_hash')
                result = self.positions_service.get_positions(account_hash)
                result['timestamp'] = timestamp
                return result
            
            elif action == 'get_positions_by_symbol':
                symbol = request.get('symbol')
                account_hash = request.get('account_hash')
                
                if not symbol:
                    return {
                        'success': False,
                        'error': 'Symbol parameter is required for get_positions_by_symbol',
                        'timestamp': timestamp
                    }
                
                result = self.positions_service.get_positions_by_symbol(symbol, account_hash)
                result['timestamp'] = timestamp
                return result
            
            else:
                return {
                    'success': False,
                    'error': f'Unknown action: {action}',
                    'available_actions': [
                        'ping', 'test_connection', 'initialize_credentials',
                        'get_linked_accounts', 'get_account_details', 'get_account_summary',
                        'get_positions', 'get_positions_by_symbol'
                    ],
                    'timestamp': timestamp
                }
                
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            return {
                'success': False,
                'error': f'Request processing error: {str(e)}',
                'timestamp': datetime.now().isoformat()
            }

def main():
    """Main function to start the server."""
    server = SchwabServer()
    
    try:
        # Check startup options in order of preference:
        # 1. Environment variables (explicit credentials)
        # 2. Valid tokens.json file (previous authentication)
        # 3. Start without credentials (initialize later)
        
        if config.is_configured():
            logger.info("Initializing server with environment credentials...")
            server.initialize_services(config.app_key, config.app_secret)
            logger.info("Server initialized with environment credentials")
            
        elif config.can_start_with_tokens():
            logger.info("Valid tokens and stored credentials found - initializing server...")
            try:
                # Get stored credentials
                app_key, app_secret, callback_url = config.get_stored_credentials()
                if app_key and app_secret:
                    server.initialize_services(app_key, app_secret, callback_url)
                    logger.info("Server initialized with stored credentials and existing tokens")
                else:
                    raise Exception("Could not retrieve stored credentials")
            except Exception as e:
                logger.error(f"Failed to initialize with stored credentials: {e}")
                logger.info("Server starting without credentials. Use 'initialize_credentials' action to set them.")
            
        else:
            logger.info("No credentials or valid tokens found.")
            logger.info("Server starting without credentials. Use 'initialize_credentials' action to set them.")
        
        # Start the server
        server.start()
        
    except KeyboardInterrupt:
        logger.info("Server interrupted by user")
    except Exception as e:
        logger.error(f"Server startup error: {str(e)}")
    finally:
        server.stop()

if __name__ == "__main__":
    main()