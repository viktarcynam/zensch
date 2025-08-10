"""
TCP Client for communicating with the Schwab API server.
Provides methods to send requests and receive responses from the server.
"""
import socket
import json
import logging
from typing import Dict, Any, Optional, Union
from datetime import datetime

from config import config
from json_parser import json_parser

logger = logging.getLogger(__name__)

class SchwabClient:
    """TCP Client for communicating with Schwab API server."""
    
    def __init__(self, host: str = None, port: int = None, timeout: int = 30):
        """
        Initialize the Schwab client.
        
        Args:
            host: Server host address
            port: Server port number
            timeout: Socket timeout in seconds
        """
        self.host = host or config.server_host
        self.port = port or config.server_port
        self.timeout = timeout
        self.socket = None
    
    def connect(self) -> bool:
        """
        Connect to the Schwab server.
        
        Returns:
            bool: True if connection successful, False otherwise
        """
        try:
            self.socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.socket.settimeout(self.timeout)
            self.socket.connect((self.host, self.port))
            logger.info(f"Connected to Schwab server at {self.host}:{self.port}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to connect to server: {str(e)}")
            return False
    
    def disconnect(self):
        """Disconnect from the server."""
        if self.socket:
            try:
                self.socket.close()
                logger.info("Disconnected from server")
            except:
                pass
            finally:
                self.socket = None
    
    def send_json_request(self, json_string: str) -> Dict[str, Any]:
        """
        Send a JSON string request to the server and return the response.
        
        Args:
            json_string: JSON string containing the request
            
        Returns:
            Dict containing server response
        """
        try:
            # Parse and format the JSON string
            format_result = json_parser.format_request(json_string)
            
            if not format_result['success']:
                return format_result
            
            # Send the formatted request
            return self.send_request(format_result['request'])
            
        except Exception as e:
            error_msg = f"Error processing JSON request: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    def send_request(self, *args) -> Dict[str, Any]:
        """
        Send a request to the server and return the response.
        
        Args:
            *args: Can be:
                   - Single dictionary: Traditional request
                   - Single JSON string: JSON request
                   - Filename (no ':' in string): Load JSON from file
                   - Multiple arguments: Combine files, JSON strings, and dictionaries
            
        Returns:
            Dict containing server response
        """
        # Handle different argument patterns
        if len(args) == 1 and isinstance(args[0], dict):
            # Traditional dictionary request
            request = args[0]
        elif len(args) == 1 and isinstance(args[0], str) and ':' in args[0]:
            # Single JSON string
            format_result = json_parser.format_request(args[0])
            if not format_result['success']:
                return format_result
            request = format_result['request']
        else:
            # Multiple arguments or filename - use new argument parsing
            format_result = json_parser.format_request_from_args(*args)
            if not format_result['success']:
                return format_result
            request = format_result['request']
        
        # Handle the formatted request
        try:
            if not self.socket:
                if not self.connect():
                    return {
                        'success': False,
                        'error': 'Failed to connect to server',
                        'timestamp': datetime.now().isoformat()
                    }
            
            # Send request
            request_json = json.dumps(request)
            self.socket.send(request_json.encode('utf-8'))
            
            # Receive response
            response_data = self.socket.recv(65536)  # Increased buffer size for larger responses
            response = json.loads(response_data.decode('utf-8'))
            
            return response
            
        except json.JSONDecodeError as e:
            error_msg = f"Invalid JSON response from server: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
            
        except socket.timeout:
            error_msg = "Request timed out"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
            
        except Exception as e:
            error_msg = f"Request failed: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg,
                'timestamp': datetime.now().isoformat()
            }
    
    def ping(self) -> Dict[str, Any]:
        """
        Ping the server to check if it's running.
        
        Returns:
            Dict containing ping response
        """
        return self.send_request({'action': 'ping'})
    
    def test_connection(self) -> Dict[str, Any]:
        """
        Test the server's connection to Schwab API.
        
        Returns:
            Dict containing connection test response
        """
        return self.send_request({'action': 'test_connection'})
    
    def initialize_credentials(self, app_key: str, app_secret: str, 
                             callback_url: str = None, tokens_file: str = None) -> Dict[str, Any]:
        """
        Initialize server with Schwab API credentials.
        
        Args:
            app_key: Schwab API app key
            app_secret: Schwab API app secret
            callback_url: OAuth callback URL
            tokens_file: Path to tokens file
            
        Returns:
            Dict containing initialization response
        """
        request = {
            'action': 'initialize_credentials',
            'app_key': app_key,
            'app_secret': app_secret
        }
        
        if callback_url:
            request['callback_url'] = callback_url
        if tokens_file:
            request['tokens_file'] = tokens_file
        
        return self.send_request(request)
    
    def get_linked_accounts(self) -> Dict[str, Any]:
        """
        Get all linked accounts.
        
        Returns:
            Dict containing linked accounts response
        """
        return self.send_request({'action': 'get_linked_accounts'})
    
    def get_account_details(self, account_hash: str = None, 
                          include_positions: bool = False) -> Dict[str, Any]:
        """
        Get account details for a specific account or all accounts.
        
        Args:
            account_hash: Specific account hash, or None for all accounts
            include_positions: Whether to include position information
            
        Returns:
            Dict containing account details response
        """
        request = {
            'action': 'get_account_details',
            'include_positions': include_positions
        }
        
        if account_hash:
            request['account_hash'] = account_hash
        
        return self.send_request(request)
    
    def get_account_summary(self, account_hash: str = None) -> Dict[str, Any]:
        """
        Get account summary (balances without positions).
        
        Args:
            account_hash: Specific account hash, or None for all accounts
            
        Returns:
            Dict containing account summary response
        """
        request = {'action': 'get_account_summary'}
        
        if account_hash:
            request['account_hash'] = account_hash
        
        return self.send_request(request)
    
    def get_positions(self, account_hash: str = None) -> Dict[str, Any]:
        """
        Get positions for a specific account or all accounts.
        
        Args:
            account_hash: Specific account hash, or None for all accounts
            
        Returns:
            Dict containing positions response
        """
        request = {'action': 'get_positions'}
        
        if account_hash:
            request['account_hash'] = account_hash
        
        return self.send_request(request)
    
    def get_positions_by_symbol(self, symbol: str, account_hash: str = None) -> Dict[str, Any]:
        """
        Get positions for a specific symbol.
        
        Args:
            symbol: Stock symbol to filter by
            account_hash: Specific account hash, or None for all accounts
            
        Returns:
            Dict containing filtered positions response
        """
        request = {
            'action': 'get_positions_by_symbol',
            'symbol': symbol
        }
        
        if account_hash:
            request['account_hash'] = account_hash
        
        return self.send_request(request)
    
    def __enter__(self):
        """Context manager entry."""
        self.connect()
        return self
    
    def __exit__(self, exc_type, exc_val, exc_tb):
        """Context manager exit."""
        self.disconnect()
    
    def get_request_template(self, action: str) -> Dict[str, Any]:
        """
        Get a JSON template for a specific action.
        
        Args:
            action: The action to get template for
            
        Returns:
            Dict containing the template
        """
        return json_parser.create_request_template(action)
    
    def get_all_templates(self) -> Dict[str, Any]:
        """
        Get templates for all available actions.
        
        Returns:
            Dict containing all templates
        """
        return json_parser.get_all_templates()
    
    def validate_json_request(self, json_string: str) -> Dict[str, Any]:
        """
        Validate a JSON request string without sending it.
        
        Args:
            json_string: JSON string to validate
            
        Returns:
            Dict containing validation result
        """
        return json_parser.format_request(json_string)
    
    def validate_request_args(self, *args) -> Dict[str, Any]:
        """
        Validate request arguments without sending them.
        
        Args:
            *args: Arguments that can be filenames, JSON strings, or dictionaries
            
        Returns:
            Dict containing validation result
        """
        return json_parser.format_request_from_args(*args)
    
    def load_json_file(self, filename: str) -> Dict[str, Any]:
        """
        Load and validate JSON from a file.
        
        Args:
            filename: Path to JSON file
            
        Returns:
            Dict containing loaded JSON or error
        """
        return json_parser.load_json_file(filename)
    
    def send_from_file(self, filename: str, *additional_args) -> Dict[str, Any]:
        """
        Send a request loaded from a JSON file, optionally combined with additional arguments.
        
        Args:
            filename: Path to JSON file
            *additional_args: Additional JSON strings or dictionaries to combine
            
        Returns:
            Dict containing server response
        """
        return self.send_request(filename, *additional_args)
        
    def get_quotes(self, symbols: Optional[Union[list, str]] = None, fields: str = "all", indicative: bool = False) -> Dict[str, Any]:
        """
        Get quotes for specified symbols. If symbols are not provided,
        the server will use the last requested symbols or a default.
        
        Args:
            symbols: Optional list/string of symbols.
            fields: Fields to include ("all", "quote", "fundamental").
            indicative: Whether to return indicative quotes.
            
        Returns:
            Dict containing quote results.
        """
        request = {
            'action': 'get_quotes',
            'symbols': symbols,
            'fields': fields,
            'indicative': indicative
        }
        
        return self.send_request(request)
    
    def get_option_chains(self, symbol: str, **kwargs) -> Dict[str, Any]:
        """
        Get option chains for a specified symbol.
        
        Args:
            symbol: Symbol to get option chain for (e.g., "AAPL", "$SPX")
            **kwargs: Additional parameters for the option chain request
                - contractType: "ALL", "CALL", or "PUT"
                - strikeCount: Number of strikes
                - includeUnderlyingQuote: Boolean to include underlying quote
                - strategy: Strategy type (SINGLE, ANALYTICAL, etc.)
                - interval: Interval value
                - strike: Strike price
                - range: Range type (ITM, ATM, OTM, etc.)
                - fromDate: Start date (datetime or "yyyy-MM-dd")
                - toDate: End date (datetime or "yyyy-MM-dd")
                - volatility: Volatility value
                - underlyingPrice: Underlying price
                - interestRate: Interest rate
                - daysToExpiration: Days to expiration
                - expMonth: Expiration month (JAN, FEB, etc.)
                - optionType: Option type
                - entitlement: Entitlement type (PN, NP, PP)
            
        Returns:
            Dict containing option chain results
        """
        request = {
            'action': 'get_option_chains',
            'symbol': symbol
        }
        
        # Add all kwargs to the request
        for key, value in kwargs.items():
            request[key] = value
        
        return self.send_request(request)
        
    def get_option_quote(self, symbol: Optional[str] = None, expiry: Optional[Union[str, int]] = None, strike: Optional[float] = None) -> Dict[str, Any]:
        """
        Get a formatted quote for a specific option strike.
        Parameters are optional and will be defaulted by the server if not provided.
        """
        request = {'action': 'get_option_quote'}
        if symbol:
            request['symbol'] = symbol
        if expiry:
            request['expiry'] = expiry
        if strike:
            request['strike'] = strike

        return self.send_request(request)

    # Stock Order Methods
    
    def place_stock_order(self, account_id: str, symbol: str, quantity: int, 
                         side: str, order_type: str = "MARKET", 
                         price: float = None, stop_price: float = None,
                         duration: str = "DAY", session: str = "NORMAL") -> Dict[str, Any]:
        """
        Place a stock order.
        
        Args:
            account_id: Account ID to place the order for
            symbol: Stock symbol
            quantity: Number of shares
            side: Order side (BUY, SELL, BUY_TO_COVER, SELL_SHORT)
            order_type: Order type (MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP)
            price: Limit price (required for LIMIT and STOP_LIMIT orders)
            stop_price: Stop price (required for STOP and STOP_LIMIT orders)
            duration: Order duration (DAY, GOOD_TILL_CANCEL, FILL_OR_KILL)
            session: Order session (NORMAL, AM, PM, SEAMLESS)
            
        Returns:
            Dict containing order result
        """
        request = {
            'action': 'place_stock_order',
            'account_id': account_id,
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'order_type': order_type,
            'duration': duration,
            'session': session
        }
        
        if price is not None:
            request['price'] = price
            
        if stop_price is not None:
            request['stop_price'] = stop_price
        
        return self.send_request(request)
    
    def cancel_stock_order(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel a stock order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to cancel
            
        Returns:
            Dict containing cancellation result
        """
        request = {
            'action': 'cancel_stock_order',
            'account_id': account_id,
            'order_id': order_id
        }
        
        return self.send_request(request)
    
    def replace_stock_order(self, account_id: str, order_id: str, 
                           symbol: str, quantity: int, side: str,
                           order_type: str = "MARKET", price: float = None,
                           stop_price: float = None, duration: str = "DAY",
                           session: str = "NORMAL") -> Dict[str, Any]:
        """
        Replace (modify) a stock order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to replace
            symbol: Stock symbol
            quantity: New quantity of shares
            side: New order side (BUY, SELL, BUY_TO_COVER, SELL_SHORT)
            order_type: New order type (MARKET, LIMIT, STOP, STOP_LIMIT, TRAILING_STOP)
            price: New limit price (required for LIMIT and STOP_LIMIT orders)
            stop_price: New stop price (required for STOP and STOP_LIMIT orders)
            duration: New order duration (DAY, GOOD_TILL_CANCEL, FILL_OR_KILL)
            session: New order session (NORMAL, AM, PM, SEAMLESS)
            
        Returns:
            Dict containing replacement result
        """
        request = {
            'action': 'replace_stock_order',
            'account_id': account_id,
            'order_id': order_id,
            'symbol': symbol,
            'quantity': quantity,
            'side': side,
            'order_type': order_type,
            'duration': duration,
            'session': session
        }
        
        if price is not None:
            request['price'] = price
            
        if stop_price is not None:
            request['stop_price'] = stop_price
        
        return self.send_request(request)
    
    def get_stock_order_details(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific stock order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to get details for
            
        Returns:
            Dict containing order details
        """
        request = {
            'action': 'get_stock_order_details',
            'account_id': account_id,
            'order_id': order_id
        }
        
        return self.send_request(request)
    
    def get_stock_orders(self, account_id: str, status: str = None, max_results: int = None) -> Dict[str, Any]:
        """
        Get all stock orders for an account, optionally filtered by status.
        
        Args:
            account_id: Account ID to get orders for
            status: Optional status filter (OPEN, FILLED, CANCELLED, etc.)
            max_results: The maximum number of orders to retrieve.
            
        Returns:
            Dict containing orders
        """
        request = {
            'action': 'get_stock_orders',
            'account_id': account_id
        }
        
        if status:
            request['status'] = status
        if max_results:
            request['max_results'] = max_results
        
        return self.send_request(request)
    
    # Option Order Methods
    
    def place_option_order(self, account_id: str, symbol: str, option_type: str,
                          expiration_date: str, strike_price: float, quantity: int,
                          side: str, order_type: str = "MARKET", price: float = None,
                          stop_price: float = None, duration: str = "DAY",
                          session: str = "NORMAL") -> Dict[str, Any]:
        """
        Place an option order.
        
        Args:
            account_id: Account ID to place the order for
            symbol: Underlying stock symbol
            option_type: Option type (CALL or PUT)
            expiration_date: Option expiration date in format YYYY-MM-DD
            strike_price: Option strike price
            quantity: Number of contracts
            side: Order side (BUY_TO_OPEN, SELL_TO_OPEN, BUY_TO_CLOSE, SELL_TO_CLOSE)
            order_type: Order type (MARKET, LIMIT, STOP, STOP_LIMIT)
            price: Limit price (required for LIMIT and STOP_LIMIT orders)
            stop_price: Stop price (required for STOP and STOP_LIMIT orders)
            duration: Order duration (DAY, GOOD_TILL_CANCEL, FILL_OR_KILL)
            session: Order session (NORMAL, AM, PM, SEAMLESS)
            
        Returns:
            Dict containing order result
        """
        request = {
            'action': 'place_option_order',
            'account_id': account_id,
            'symbol': symbol,
            'option_type': option_type,
            'expiration_date': expiration_date,
            'strike_price': strike_price,
            'quantity': quantity,
            'side': side,
            'order_type': order_type,
            'duration': duration,
            'session': session
        }
        
        if price is not None:
            request['price'] = price
            
        if stop_price is not None:
            request['stop_price'] = stop_price
        
        return self.send_request(request)
    
    def cancel_option_order(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel an option order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to cancel
            
        Returns:
            Dict containing cancellation result
        """
        request = {
            'action': 'cancel_option_order',
            'account_id': account_id,
            'order_id': order_id
        }
        
        return self.send_request(request)
    
    def replace_option_order(self, account_id: str, order_id: str, symbol: str,
                            option_type: str, expiration_date: str, strike_price: float,
                            quantity: int, side: str, order_type: str = "MARKET",
                            price: float = None, stop_price: float = None,
                            duration: str = "DAY", session: str = "NORMAL") -> Dict[str, Any]:
        """
        Replace (modify) an option order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to replace
            symbol: Underlying stock symbol
            option_type: Option type (CALL or PUT)
            expiration_date: Option expiration date in format YYYY-MM-DD
            strike_price: Option strike price
            quantity: Number of contracts
            side: Order side (BUY_TO_OPEN, SELL_TO_OPEN, BUY_TO_CLOSE, SELL_TO_CLOSE)
            order_type: Order type (MARKET, LIMIT, STOP, STOP_LIMIT)
            price: Limit price (required for LIMIT and STOP_LIMIT orders)
            stop_price: Stop price (required for STOP and STOP_LIMIT orders)
            duration: Order duration (DAY, GOOD_TILL_CANCEL, FILL_OR_KILL)
            session: Order session (NORMAL, AM, PM, SEAMLESS)
            
        Returns:
            Dict containing replacement result
        """
        request = {
            'action': 'replace_option_order',
            'account_id': account_id,
            'order_id': order_id,
            'symbol': symbol,
            'option_type': option_type,
            'expiration_date': expiration_date,
            'strike_price': strike_price,
            'quantity': quantity,
            'side': side,
            'order_type': order_type,
            'duration': duration,
            'session': session
        }
        
        if price is not None:
            request['price'] = price
            
        if stop_price is not None:
            request['stop_price'] = stop_price
        
        return self.send_request(request)
    
    def get_option_order_details(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific option order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to get details for
            
        Returns:
            Dict containing order details
        """
        request = {
            'action': 'get_option_order_details',
            'account_id': account_id,
            'order_id': order_id
        }
        
        return self.send_request(request)
    
    def get_option_orders(self, account_id: str, status: str = None, max_results: int = None) -> Dict[str, Any]:
        """
        Get all option orders for an account, optionally filtered by status.
        
        Args:
            account_id: Account ID to get orders for
            status: Optional status filter (OPEN, FILLED, CANCELLED, etc.)
            max_results: The maximum number of orders to retrieve.
            
        Returns:
            Dict containing orders
        """
        request = {
            'action': 'get_option_orders',
            'account_id': account_id
        }
        
        if status:
            request['status'] = status
        if max_results:
            request['max_results'] = max_results
        
        return self.send_request(request)

def main():
    """Main function that handles command line arguments or runs demo."""
    import sys
    import os
    
    # Configure logging
    logging.basicConfig(level=logging.INFO)
    
    if len(sys.argv) == 1:
        # No arguments - run demo mode
        demo_mode()
        return
    
    args = sys.argv[1:]
    
    # Check if first argument is a filename, JSON string, or key:value
    first_arg = args[0]
    is_json_string = first_arg.startswith('{') and first_arg.endswith('}')
    is_filename = ':' not in first_arg and not is_json_string
    
    try:
        if is_json_string and len(args) == 1:
            # Mode 4: Direct JSON string - send as-is
            with SchwabClient() as client:
                print(f"Sending request: {first_arg}")
                response = client.send_request(first_arg)
                print(json.dumps(response, indent=2))
                
        elif is_filename and len(args) == 1:
            # Mode 1: Filename only - load complete JSON from file
            if not os.path.exists(first_arg):
                print(f"Error: File '{first_arg}' not found")
                return
            
            with SchwabClient() as client:
                response = client.send_from_file(first_arg)
                print(json.dumps(response, indent=2))
                
        elif is_filename and len(args) > 1:
            # Mode 2: Filename + key:value pairs - load JSON and override/add values
            if not os.path.exists(first_arg):
                print(f"Error: File '{first_arg}' not found")
                return
            
            # Parse key:value pairs from remaining arguments
            overrides = {}
            for arg in args[1:]:
                if ':' not in arg:
                    print(f"Error: Invalid key:value format '{arg}'. Expected 'key:value'")
                    return
                key, value = arg.split(':', 1)  # Split only on first ':'
                overrides[key] = parse_value(value)
            
            with SchwabClient() as client:
                # Load base JSON from file
                base_request = client.load_json_file(first_arg)
                if not base_request.get('success', False):
                    print(f"Error loading file: {base_request.get('error', 'Unknown error')}")
                    return
                
                # Merge overrides into base request
                request_data = base_request['data']
                request_data.update(overrides)
                
                print(f"Sending request: {json.dumps(request_data)}")
                response = client.send_request(json.dumps(request_data))
                print(json.dumps(response, indent=2))
                
        else:
            # Mode 3: Key:value pairs only - build JSON from arguments
            request_data = {}
            for arg in args:
                if ':' not in arg:
                    print(f"Error: Invalid key:value format '{arg}'. Expected 'key:value'")
                    return
                key, value = arg.split(':', 1)  # Split only on first ':'
                request_data[key] = parse_value(value)
            
            with SchwabClient() as client:
                print(f"Sending request: {json.dumps(request_data)}")
                response = client.send_request(json.dumps(request_data))
                print(json.dumps(response, indent=2))
                
    except Exception as e:
        print(f"Error processing request: {e}")

def parse_value(value_str):
    """Parse a string value, attempting to convert to appropriate type."""
    # Try to parse as JSON first (for objects, arrays, booleans, null)
    try:
        return json.loads(value_str)
    except json.JSONDecodeError:
        # If not valid JSON, treat as string
        return value_str

def demo_mode():
    """Example usage of the Schwab client."""
    print("=== SCHWAB CLIENT DEMO MODE ===")
    print("Usage modes:")
    print("1. From file:           python client.py request.json")
    print("2. File + overrides:    python client.py request.json action:ping account_hash:ABC123")
    print("3. Key:value pairs:     python client.py action:ping")
    print("4. Direct JSON:         python client.py '{\"action\": \"ping\"}'")
    print("\nNo arguments provided, running demo...\n")
    
    # Example usage
    with SchwabClient() as client:
        # Show available templates
        print("=== Available Request Templates ===")
        templates = client.get_all_templates()
        if templates['success']:
            for action, template in templates['templates'].items():
                print(f"\n{action.upper()}:")
                print(json.dumps(template, indent=2))
        
        # Ping server using JSON string
        print("\n=== Ping Server (JSON String) ===")
        ping_json = '{"action": "ping"}'
        response = client.send_request(ping_json)
        print(json.dumps(response, indent=2))
        
        # Test connection using JSON string (will fail if credentials not set)
        print("\n=== Test Connection (JSON String) ===")
        test_json = '{"action": "test_connection"}'
        response = client.send_request(test_json)
        print(json.dumps(response, indent=2))
        
        # Example: Validate JSON without sending
        print("\n=== Validate JSON Request ===")
        sample_json = '{"action": "get_positions", "account_hash": "optional"}'
        validation = client.validate_json_request(sample_json)
        print(json.dumps(validation, indent=2))

if __name__ == "__main__":
    main()