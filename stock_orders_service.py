#!/usr/bin/env python3
"""
Stock Orders Service Module for Schwab API Client-Server System.
Handles stock order operations using the schwabdev library.
"""
import logging
import sqlite3
from typing import Dict, Any, Optional, Union, List
from datetime import datetime, timedelta
from state_manager import state_manager
from account_service import AccountService

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('stock_orders_service')

# Initialize SQLite database for order logging
def init_order_database():
    """Initialize the SQLite database for order logging."""
    conn = sqlite3.connect('orders.db')
    cursor = conn.cursor()
    
    # Create orders table if it doesn't exist
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS orders (
        order_id TEXT PRIMARY KEY,
        account_id TEXT,
        symbol TEXT,
        instrument_type TEXT,
        side TEXT,
        quantity REAL,
        order_type TEXT,
        limit_price REAL,
        stop_price REAL,
        execution_price REAL,
        underlying_price REAL,
        status TEXT,
        time_executed TEXT,
        option_type TEXT,
        expiration_date TEXT,
        strike_price REAL
    )
    ''')
    
    conn.commit()
    conn.close()
    logger.info("Order database initialized")

# Initialize the database
init_order_database()

def log_order_to_db(order_data: Dict[str, Any]):
    """
    Log order information to SQLite database.
    
    Args:
        order_data: Dictionary containing order information
    """
    try:
        conn = sqlite3.connect('orders.db')
        cursor = conn.cursor()
        
        # Extract order information
        order_id = order_data.get('order_id', '')
        account_id = order_data.get('account_id', '')
        symbol = order_data.get('symbol', '')
        instrument_type = order_data.get('instrument_type', 'EQUITY')
        side = order_data.get('side', '')
        quantity = order_data.get('quantity', 0)
        order_type = order_data.get('order_type', '')
        limit_price = order_data.get('limit_price', 0.0)
        stop_price = order_data.get('stop_price', 0.0)
        execution_price = order_data.get('execution_price', 0.0)
        underlying_price = order_data.get('underlying_price', 0.0)
        status = order_data.get('status', 'PENDING')
        time_executed = order_data.get('time_executed', datetime.now().isoformat())
        option_type = order_data.get('option_type', '')
        expiration_date = order_data.get('expiration_date', '')
        strike_price = order_data.get('strike_price', 0.0)
        
        # Insert or update order in database
        cursor.execute('''
        INSERT OR REPLACE INTO orders (
            order_id, account_id, symbol, instrument_type, side, quantity, 
            order_type, limit_price, stop_price, execution_price, underlying_price,
            status, time_executed, option_type, expiration_date, strike_price
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        ''', (
            order_id, account_id, symbol, instrument_type, side, quantity,
            order_type, limit_price, stop_price, execution_price, underlying_price,
            status, time_executed, option_type, expiration_date, strike_price
        ))
        
        conn.commit()
        conn.close()
        logger.info(f"Order {order_id} logged to database")
    except Exception as e:
        logger.error(f"Error logging order to database: {str(e)}")

# Valid parameter values for validation
VALID_ORDER_TYPES = ["MARKET", "LIMIT", "STOP", "STOP_LIMIT", "TRAILING_STOP"]
VALID_SESSION_TYPES = ["NORMAL", "AM", "PM", "SEAMLESS"]
VALID_DURATIONS = ["DAY", "GOOD_TILL_CANCEL", "FILL_OR_KILL"]
VALID_SIDES = ["BUY", "SELL", "BUY_TO_COVER", "SELL_SHORT"]

class StockOrdersService:
    """Service for handling stock order operations."""
    
    def __init__(self, schwab_client=None, account_service=None):
        """
        Initialize the stock orders service.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
            account_service: Instance of AccountService
        """
        self.schwab_client = schwab_client
        self.account_service = account_service
        logger.info("Stock orders service initialized")
    
    def set_client(self, schwab_client, account_service=None):
        """
        Set the schwabdev client instance.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
            account_service: Instance of AccountService
        """
        self.schwab_client = schwab_client
        if account_service:
            self.account_service = account_service
        logger.info("Schwab client set in stock orders service")
    
    def place_stock_order(self, symbol: str, quantity: int,
                         side: str, order_type: str = "LIMIT", 
                         price: float = None, stop_price: float = None,
                         duration: str = "DAY", session: str = "NORMAL",
                         account_id: Optional[str] = None) -> Dict[str, Any]:
        """
        Place a stock order. Default order type is LIMIT.
        
        Args:
            symbol: Stock symbol
            quantity: Number of shares
            side: Order side (BUY, SELL, BUY_TO_COVER, SELL_SHORT)
            order_type: Order type (LIMIT, MARKET, STOP, STOP_LIMIT, TRAILING_STOP)
            price: Limit price (required for LIMIT and STOP_LIMIT orders)
            stop_price: Stop price (required for STOP and STOP_LIMIT orders)
            duration: Order duration (DAY, GOOD_TILL_CANCEL, FILL_OR_KILL)
            session: Order session (NORMAL, AM, PM, SEAMLESS)
            
        Returns:
            Dictionary with order result or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in stock orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            if not account_id:
                if not self.account_service:
                    return {
                        "success": False,
                        "error": "Account service not initialized."
                    }
                account_id = state_manager.get_primary_account_hash(self.account_service)
                if not account_id:
                    return {
                        "success": False,
                        "error": "Could not determine account ID. Please specify one."
                    }

            # If order type is LIMIT but no price is provided, try to get current price
            if order_type == "LIMIT" and price is None:
                try:
                    # Get current quote for the symbol to use as limit price
                    quote_response = self.schwab_client.quote(symbol)
                    if hasattr(quote_response, 'json'):
                        quote_data = quote_response.json()
                        # Use last price or bid price as limit price
                        if symbol in quote_data and 'quote' in quote_data[symbol]:
                            quote = quote_data[symbol]['quote']
                            if 'lastPrice' in quote:
                                price = quote['lastPrice']
                            elif 'bidPrice' in quote:
                                price = quote['bidPrice']
                            else:
                                logger.warning(f"Could not determine limit price for {symbol}, defaulting to MARKET order")
                                order_type = "MARKET"
                        else:
                            logger.warning(f"Could not determine limit price for {symbol}, defaulting to MARKET order")
                            order_type = "MARKET"
                    else:
                        logger.warning(f"Could not get quote for {symbol}, defaulting to MARKET order")
                        order_type = "MARKET"
                except Exception as quote_error:
                    logger.warning(f"Error getting quote for limit price: {str(quote_error)}, defaulting to MARKET order")
                    order_type = "MARKET"
            
            logger.info(f"Placing stock order for {symbol}, {quantity} shares, {side}, {order_type}" + 
                       (f" at ${price}" if price is not None else ""))
            
            # Create order parameters
            order_params = {
                "orderType": order_type,
                "session": session,
                "duration": duration,
                "orderStrategyType": "SINGLE",
                "orderLegCollection": [
                    {
                        "instruction": side,
                        "quantity": quantity,
                        "instrument": {
                            "symbol": symbol,
                            "assetType": "EQUITY"
                        }
                    }
                ]
            }
            
            # Add price for LIMIT and STOP_LIMIT orders
            if order_type in ["LIMIT", "STOP_LIMIT"] and price is not None:
                order_params["price"] = price
                
            # Add stop price for STOP and STOP_LIMIT orders
            if order_type in ["STOP", "STOP_LIMIT"] and stop_price is not None:
                order_params["stopPrice"] = stop_price
            
            # Place the order
            response = self.schwab_client.order_place(account_id, order_params)
            
            # Process the response
            if hasattr(response, 'json'):
                order_data = response.json()
                logger.info(f"Successfully placed stock order for {symbol}")
                
                # Extract order ID from response
                order_id = None
                if 'orderId' in order_data:
                    order_id = order_data['orderId']
                elif 'order_id' in order_data:
                    order_id = order_data['order_id']
                
                # Log order to database
                if order_id:
                    log_data = {
                        'order_id': order_id,
                        'account_id': account_id,
                        'symbol': symbol,
                        'instrument_type': 'EQUITY',
                        'side': side,
                        'quantity': quantity,
                        'order_type': order_type,
                        'limit_price': price,
                        'stop_price': stop_price,
                        'status': 'PLACED',
                        'time_executed': datetime.now().isoformat()
                    }
                    log_order_to_db(log_data)
                
                return {
                    "success": True,
                    "data": order_data,
                    "message": f"Stock order for {symbol} placed successfully"
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully placed stock order for {symbol}")
                
                # Extract order ID from response if possible
                order_id = None
                if hasattr(response, 'get'):
                    order_id = response.get('orderId') or response.get('order_id')
                
                # Log order to database
                if order_id:
                    log_data = {
                        'order_id': order_id,
                        'account_id': account_id,
                        'symbol': symbol,
                        'instrument_type': 'EQUITY',
                        'side': side,
                        'quantity': quantity,
                        'order_type': order_type,
                        'limit_price': price,
                        'stop_price': stop_price,
                        'status': 'PLACED',
                        'time_executed': datetime.now().isoformat()
                    }
                    log_order_to_db(log_data)
                
                return {
                    "success": True,
                    "data": response,
                    "message": f"Stock order for {symbol} placed successfully"
                }
                
        except Exception as e:
            logger.error(f"Error placing stock order: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to place stock order: {str(e)}"
            }
    
    def cancel_stock_order(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel a stock order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to cancel
            
        Returns:
            Dictionary with cancellation result or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in stock orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Cancelling stock order {order_id} for account {account_id}")
            
            # Cancel the order
            response = self.schwab_client.order_cancel(account_id, order_id)
            
            # Process the response
            if hasattr(response, 'status_code'):
                if response.status_code == 200:
                    logger.info(f"Successfully cancelled stock order {order_id}")
                    return {
                        "success": True,
                        "message": f"Stock order {order_id} cancelled successfully"
                    }
                else:
                    logger.error(f"Failed to cancel stock order: {response.text}")
                    return {
                        "success": False,
                        "error": f"Failed to cancel stock order: {response.text}"
                    }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully cancelled stock order {order_id}")
                return {
                    "success": True,
                    "message": f"Stock order {order_id} cancelled successfully"
                }
                
        except Exception as e:
            logger.error(f"Error cancelling stock order: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to cancel stock order: {str(e)}"
            }
    
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
            Dictionary with replacement result or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in stock orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Replacing stock order {order_id} for {symbol}, {quantity} shares, {side}")
            
            # Create replacement order parameters
            order_params = {
                "orderType": order_type,
                "session": session,
                "duration": duration,
                "orderStrategyType": "SINGLE",
                "orderLegCollection": [
                    {
                        "instruction": side,
                        "quantity": quantity,
                        "instrument": {
                            "symbol": symbol,
                            "assetType": "EQUITY"
                        }
                    }
                ]
            }
            
            # Add price for LIMIT and STOP_LIMIT orders
            if order_type in ["LIMIT", "STOP_LIMIT"] and price is not None:
                order_params["price"] = price
                
            # Add stop price for STOP and STOP_LIMIT orders
            if order_type in ["STOP", "STOP_LIMIT"] and stop_price is not None:
                order_params["stopPrice"] = stop_price
            
            # Replace the order
            response = self.schwab_client.order_replace(account_id, order_id, order_params)
            
            # Process the response
            if hasattr(response, 'json'):
                order_data = response.json()
                logger.info(f"Successfully replaced stock order for {symbol}")
                return {
                    "success": True,
                    "data": order_data,
                    "message": f"Stock order for {symbol} replaced successfully"
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully replaced stock order for {symbol}")
                return {
                    "success": True,
                    "data": response,
                    "message": f"Stock order for {symbol} replaced successfully"
                }
                
        except Exception as e:
            logger.error(f"Error replacing stock order: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to replace stock order: {str(e)}"
            }
    
    def get_stock_order_details(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific stock order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to get details for
            
        Returns:
            Dictionary with order details or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in stock orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Getting details for stock order {order_id} in account {account_id}")
            
            # Get order details
            response = self.schwab_client.order_details(account_id, order_id)
            
            # Process the response
            if hasattr(response, 'json'):
                order_data = response.json()
                logger.info(f"Successfully retrieved details for stock order {order_id}")
                return {
                    "success": True,
                    "data": order_data
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully retrieved details for stock order {order_id}")
                return {
                    "success": True,
                    "data": response
                }
                
        except Exception as e:
            logger.error(f"Error getting stock order details: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get stock order details: {str(e)}"
            }
    
    def get_stock_orders(self, account_id: str, status: str = None) -> Dict[str, Any]:
        """
        Get all stock orders for an account, optionally filtered by status.
        
        Args:
            account_id: Account ID to get orders for
            status: Optional status filter (OPEN, FILLED, CANCELLED, etc.)
            
        Returns:
            Dictionary with orders or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in stock orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Getting stock orders for account {account_id}")
            
            # Get orders
            to_date = datetime.now()
            from_date = to_date - timedelta(days=90)
            response = self.schwab_client.account_orders(account_id, from_date, to_date, status=status)
            
            # Process the response
            if hasattr(response, 'json'):
                orders_data = response.json()
                logger.info(f"Successfully retrieved stock orders for account {account_id}")
                return {
                    "success": True,
                    "data": orders_data
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully retrieved stock orders for account {account_id}")
                return {
                    "success": True,
                    "data": response
                }
                
        except Exception as e:
            logger.error(f"Error getting stock orders: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get stock orders: {str(e)}"
            }
    
    def validate_stock_order_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a stock order request.
        
        Args:
            request_data: Dictionary containing request parameters
            
        Returns:
            Dictionary with validation results
        """
        # Check required parameters
        required_params = ['account_id', 'symbol', 'quantity', 'side']
        missing_params = [param for param in required_params if param not in request_data]
        
        if missing_params:
            return {
                "success": False,
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }
        
        # Validate side
        if request_data['side'] not in VALID_SIDES:
            return {
                "success": False,
                "error": f"Invalid side: {request_data['side']}. Valid options are: {', '.join(VALID_SIDES)}"
            }
        
        # Validate order_type if provided
        if 'order_type' in request_data and request_data['order_type'] not in VALID_ORDER_TYPES:
            return {
                "success": False,
                "error": f"Invalid order_type: {request_data['order_type']}. Valid options are: {', '.join(VALID_ORDER_TYPES)}"
            }
        
        # Validate duration if provided
        if 'duration' in request_data and request_data['duration'] not in VALID_DURATIONS:
            return {
                "success": False,
                "error": f"Invalid duration: {request_data['duration']}. Valid options are: {', '.join(VALID_DURATIONS)}"
            }
        
        # Validate session if provided
        if 'session' in request_data and request_data['session'] not in VALID_SESSION_TYPES:
            return {
                "success": False,
                "error": f"Invalid session: {request_data['session']}. Valid options are: {', '.join(VALID_SESSION_TYPES)}"
            }
        
        # Validate price requirements based on order type
        order_type = request_data.get('order_type', 'MARKET')
        
        if order_type in ['LIMIT', 'STOP_LIMIT'] and 'price' not in request_data:
            return {
                "success": False,
                "error": f"Price is required for {order_type} orders"
            }
        
        if order_type in ['STOP', 'STOP_LIMIT'] and 'stop_price' not in request_data:
            return {
                "success": False,
                "error": f"Stop price is required for {order_type} orders"
            }
        
        # Validate numeric values
        try:
            quantity = int(request_data['quantity'])
            if quantity <= 0:
                return {
                    "success": False,
                    "error": "Quantity must be a positive integer"
                }
        except ValueError:
            return {
                "success": False,
                "error": "Quantity must be a valid integer"
            }
        
        if 'price' in request_data:
            try:
                price = float(request_data['price'])
                if price <= 0:
                    return {
                        "success": False,
                        "error": "Price must be a positive number"
                    }
            except ValueError:
                return {
                    "success": False,
                    "error": "Price must be a valid number"
                }
        
        if 'stop_price' in request_data:
            try:
                stop_price = float(request_data['stop_price'])
                if stop_price <= 0:
                    return {
                        "success": False,
                        "error": "Stop price must be a positive number"
                    }
            except ValueError:
                return {
                    "success": False,
                    "error": "Stop price must be a valid number"
                }
        
        # Create validated parameters dictionary
        validated_params = {
            'account_id': request_data['account_id'],
            'symbol': request_data['symbol'],
            'quantity': int(request_data['quantity']),
            'side': request_data['side'],
            'order_type': request_data.get('order_type', 'MARKET'),
            'duration': request_data.get('duration', 'DAY'),
            'session': request_data.get('session', 'NORMAL')
        }
        
        if 'price' in request_data:
            validated_params['price'] = float(request_data['price'])
        
        if 'stop_price' in request_data:
            validated_params['stop_price'] = float(request_data['stop_price'])
        
        return {
            "success": True,
            "validated_params": validated_params
        }
    
    def validate_order_id_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a request that requires account_id and order_id.
        
        Args:
            request_data: Dictionary containing request parameters
            
        Returns:
            Dictionary with validation results
        """
        # Check required parameters
        required_params = ['account_id', 'order_id']
        missing_params = [param for param in required_params if param not in request_data]
        
        if missing_params:
            return {
                "success": False,
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }
        
        return {
            "success": True,
            "validated_params": {
                'account_id': request_data['account_id'],
                'order_id': request_data['order_id']
            }
        }

# Create a singleton instance
stock_orders_service = StockOrdersService()