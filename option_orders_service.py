#!/usr/bin/env python3
"""
Option Orders Service Module for Schwab API Client-Server System.
Handles option order operations using the schwabdev library.
"""
import logging
import sqlite3
from typing import Dict, Any, Optional, Union, List
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('option_orders_service')

# Import the order logging function from stock_orders_service
from stock_orders_service import log_order_to_db

# Valid parameter values for validation
VALID_ORDER_TYPES = ["MARKET", "LIMIT", "STOP", "STOP_LIMIT"]
VALID_SESSION_TYPES = ["NORMAL", "AM", "PM", "SEAMLESS"]
VALID_DURATIONS = ["DAY", "GOOD_TILL_CANCEL", "FILL_OR_KILL"]
VALID_OPTION_SIDES = ["BUY_TO_OPEN", "SELL_TO_OPEN", "BUY_TO_CLOSE", "SELL_TO_CLOSE"]
VALID_OPTION_TYPES = ["CALL", "PUT"]

class OptionOrdersService:
    """Service for handling option order operations."""
    
    def __init__(self, schwab_client=None):
        """
        Initialize the option orders service.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
        """
        self.schwab_client = schwab_client
        logger.info("Option orders service initialized")
    
    def set_client(self, schwab_client):
        """
        Set the schwabdev client instance.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
        """
        self.schwab_client = schwab_client
        logger.info("Schwab client set in option orders service")
    
    def place_option_order(self, account_id: str, symbol: str, option_type: str,
                          expiration_date: str, strike_price: float, quantity: int,
                          side: str, order_type: str = "LIMIT", price: float = None,
                          stop_price: float = None, duration: str = "DAY",
                          session: str = "NORMAL") -> Dict[str, Any]:
        """
        Place an option order. Default order type is LIMIT.
        
        Args:
            account_id: Account ID to place the order for
            symbol: Underlying stock symbol
            option_type: Option type (CALL or PUT)
            expiration_date: Option expiration date in format YYYY-MM-DD
            strike_price: Option strike price
            quantity: Number of contracts
            side: Order side (BUY_TO_OPEN, SELL_TO_OPEN, BUY_TO_CLOSE, SELL_TO_CLOSE)
            order_type: Order type (LIMIT, MARKET, STOP, STOP_LIMIT)
            price: Limit price (required for LIMIT and STOP_LIMIT orders)
            stop_price: Stop price (required for STOP and STOP_LIMIT orders)
            duration: Order duration (DAY, GOOD_TILL_CANCEL, FILL_OR_KILL)
            session: Order session (NORMAL, AM, PM, SEAMLESS)
            
        Returns:
            Dictionary with order result or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in option orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            # Format the option symbol
            option_symbol = self._format_option_symbol(symbol, expiration_date, strike_price, option_type)
            
            # If order type is LIMIT but no price is provided, try to get current price
            if order_type == "LIMIT" and price is None:
                try:
                    # Get current option chain for the symbol to use as limit price
                    chain_response = self.schwab_client.get_option_chain(
                        symbol, 
                        contractType=option_type,
                        strike=strike_price,
                        fromDate=expiration_date,
                        toDate=expiration_date
                    )
                    
                    if hasattr(chain_response, 'json'):
                        chain_data = chain_response.json()
                        # Try to find the specific option contract
                        option_price = None
                        
                        # Navigate through the option chain structure to find the price
                        # This will depend on the exact structure returned by the API
                        if 'callExpDateMap' in chain_data and option_type == "CALL":
                            for date_key, strikes in chain_data['callExpDateMap'].items():
                                if str(strike_price) in strikes:
                                    option_contract = strikes[str(strike_price)][0]
                                    if side in ["BUY_TO_OPEN", "BUY_TO_CLOSE"]:
                                        option_price = option_contract.get('ask')
                                    else:  # SELL_TO_OPEN, SELL_TO_CLOSE
                                        option_price = option_contract.get('bid')
                                    break
                        
                        elif 'putExpDateMap' in chain_data and option_type == "PUT":
                            for date_key, strikes in chain_data['putExpDateMap'].items():
                                if str(strike_price) in strikes:
                                    option_contract = strikes[str(strike_price)][0]
                                    if side in ["BUY_TO_OPEN", "BUY_TO_CLOSE"]:
                                        option_price = option_contract.get('ask')
                                    else:  # SELL_TO_OPEN, SELL_TO_CLOSE
                                        option_price = option_contract.get('bid')
                                    break
                        
                        if option_price:
                            price = option_price
                        else:
                            logger.warning(f"Could not determine limit price for option, defaulting to MARKET order")
                            order_type = "MARKET"
                    else:
                        logger.warning(f"Could not get option chain, defaulting to MARKET order")
                        order_type = "MARKET"
                except Exception as chain_error:
                    logger.warning(f"Error getting option chain for limit price: {str(chain_error)}, defaulting to MARKET order")
                    order_type = "MARKET"
            
            # Get underlying stock price for logging
            underlying_price = None
            try:
                quote_response = self.schwab_client.get_quote(symbol)
                if hasattr(quote_response, 'json'):
                    quote_data = quote_response.json()
                    underlying_price = quote_data.get('lastPrice')
            except Exception as quote_error:
                logger.warning(f"Error getting underlying stock price: {str(quote_error)}")
            
            logger.info(f"Placing option order for {symbol} {option_type} {strike_price} {expiration_date}, " +
                       f"{quantity} contracts, {side}, {order_type}" +
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
                            "symbol": option_symbol,
                            "assetType": "OPTION"
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
            response = self.schwab_client.place_order(account_id, order_params)
            
            # Process the response
            if hasattr(response, 'json'):
                order_data = response.json()
                logger.info(f"Successfully placed option order for {option_symbol}")
                
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
                        'instrument_type': 'OPTION',
                        'option_type': option_type,
                        'expiration_date': expiration_date,
                        'strike_price': strike_price,
                        'side': side,
                        'quantity': quantity,
                        'order_type': order_type,
                        'limit_price': price,
                        'stop_price': stop_price,
                        'underlying_price': underlying_price,
                        'status': 'PLACED',
                        'time_executed': datetime.now().isoformat()
                    }
                    log_order_to_db(log_data)
                
                return {
                    "success": True,
                    "data": order_data,
                    "message": f"Option order for {option_symbol} placed successfully"
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully placed option order for {option_symbol}")
                
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
                        'instrument_type': 'OPTION',
                        'option_type': option_type,
                        'expiration_date': expiration_date,
                        'strike_price': strike_price,
                        'side': side,
                        'quantity': quantity,
                        'order_type': order_type,
                        'limit_price': price,
                        'stop_price': stop_price,
                        'underlying_price': underlying_price,
                        'status': 'PLACED',
                        'time_executed': datetime.now().isoformat()
                    }
                    log_order_to_db(log_data)
                
                return {
                    "success": True,
                    "data": response,
                    "message": f"Option order for {option_symbol} placed successfully"
                }
                
        except Exception as e:
            logger.error(f"Error placing option order: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to place option order: {str(e)}"
            }
    
    def cancel_option_order(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        Cancel an option order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to cancel
            
        Returns:
            Dictionary with cancellation result or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in option orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Cancelling option order {order_id} for account {account_id}")
            
            # Cancel the order
            response = self.schwab_client.cancel_order(account_id, order_id)
            
            # Process the response
            if hasattr(response, 'status_code'):
                if response.status_code == 200:
                    logger.info(f"Successfully cancelled option order {order_id}")
                    return {
                        "success": True,
                        "message": f"Option order {order_id} cancelled successfully"
                    }
                else:
                    logger.error(f"Failed to cancel option order: {response.text}")
                    return {
                        "success": False,
                        "error": f"Failed to cancel option order: {response.text}"
                    }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully cancelled option order {order_id}")
                return {
                    "success": True,
                    "message": f"Option order {order_id} cancelled successfully"
                }
                
        except Exception as e:
            logger.error(f"Error cancelling option order: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to cancel option order: {str(e)}"
            }
    
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
            Dictionary with replacement result or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in option orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Replacing option order {order_id}")
            
            # Format the option symbol
            option_symbol = self._format_option_symbol(symbol, expiration_date, strike_price, option_type)
            
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
                            "symbol": option_symbol,
                            "assetType": "OPTION"
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
            response = self.schwab_client.replace_order(account_id, order_id, order_params)
            
            # Process the response
            if hasattr(response, 'json'):
                order_data = response.json()
                logger.info(f"Successfully replaced option order for {option_symbol}")
                return {
                    "success": True,
                    "data": order_data,
                    "message": f"Option order for {option_symbol} replaced successfully"
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully replaced option order for {option_symbol}")
                return {
                    "success": True,
                    "data": response,
                    "message": f"Option order for {option_symbol} replaced successfully"
                }
                
        except Exception as e:
            logger.error(f"Error replacing option order: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to replace option order: {str(e)}"
            }
    
    def get_option_order_details(self, account_id: str, order_id: str) -> Dict[str, Any]:
        """
        Get details of a specific option order.
        
        Args:
            account_id: Account ID the order belongs to
            order_id: Order ID to get details for
            
        Returns:
            Dictionary with order details or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in option orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Getting details for option order {order_id} in account {account_id}")
            
            # Get order details
            response = self.schwab_client.get_order(account_id, order_id)
            
            # Process the response
            if hasattr(response, 'json'):
                order_data = response.json()
                logger.info(f"Successfully retrieved details for option order {order_id}")
                return {
                    "success": True,
                    "data": order_data
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully retrieved details for option order {order_id}")
                return {
                    "success": True,
                    "data": response
                }
                
        except Exception as e:
            logger.error(f"Error getting option order details: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get option order details: {str(e)}"
            }
    
    def get_option_orders(self, account_id: str, status: str = None) -> Dict[str, Any]:
        """
        Get all option orders for an account, optionally filtered by status.
        
        Args:
            account_id: Account ID to get orders for
            status: Optional status filter (OPEN, FILLED, CANCELLED, etc.)
            
        Returns:
            Dictionary with orders or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in option orders service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Getting option orders for account {account_id}")
            
            # Get orders
            response = self.schwab_client.get_orders(account_id, status=status)
            
            # Process the response and filter for option orders only
            if hasattr(response, 'json'):
                all_orders = response.json()
                
                # Filter for option orders only
                option_orders = []
                if isinstance(all_orders, list):
                    for order in all_orders:
                        # Check if this is an option order
                        if self._is_option_order(order):
                            option_orders.append(order)
                
                logger.info(f"Successfully retrieved {len(option_orders)} option orders for account {account_id}")
                return {
                    "success": True,
                    "data": option_orders
                }
            else:
                # Handle case where response is already parsed
                # Note: In this case, we can't filter for option orders only
                logger.info(f"Successfully retrieved orders for account {account_id}")
                return {
                    "success": True,
                    "data": response,
                    "message": "Note: Could not filter for option orders only"
                }
                
        except Exception as e:
            logger.error(f"Error getting option orders: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get option orders: {str(e)}"
            }
    
    def validate_option_order_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate an option order request.
        
        Args:
            request_data: Dictionary containing request parameters
            
        Returns:
            Dictionary with validation results
        """
        # Check required parameters
        required_params = ['account_id', 'symbol', 'option_type', 'expiration_date', 
                          'strike_price', 'quantity', 'side']
        missing_params = [param for param in required_params if param not in request_data]
        
        if missing_params:
            return {
                "success": False,
                "error": f"Missing required parameters: {', '.join(missing_params)}"
            }
        
        # Validate option_type
        if request_data['option_type'] not in VALID_OPTION_TYPES:
            return {
                "success": False,
                "error": f"Invalid option_type: {request_data['option_type']}. Valid options are: {', '.join(VALID_OPTION_TYPES)}"
            }
        
        # Validate side
        if request_data['side'] not in VALID_OPTION_SIDES:
            return {
                "success": False,
                "error": f"Invalid side: {request_data['side']}. Valid options are: {', '.join(VALID_OPTION_SIDES)}"
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
        
        # Validate expiration date format
        try:
            datetime.strptime(request_data['expiration_date'], '%Y-%m-%d')
        except ValueError:
            return {
                "success": False,
                "error": "Invalid expiration_date format. Use YYYY-MM-DD format."
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
        
        try:
            strike_price = float(request_data['strike_price'])
            if strike_price <= 0:
                return {
                    "success": False,
                    "error": "Strike price must be a positive number"
                }
        except ValueError:
            return {
                "success": False,
                "error": "Strike price must be a valid number"
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
            'option_type': request_data['option_type'],
            'expiration_date': request_data['expiration_date'],
            'strike_price': float(request_data['strike_price']),
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
    
    def _format_option_symbol(self, symbol: str, expiration_date: str, strike_price: float, option_type: str) -> str:
        """
        Format an option symbol in the format expected by Schwab API.
        
        Args:
            symbol: Underlying stock symbol
            expiration_date: Option expiration date in format YYYY-MM-DD
            strike_price: Option strike price
            option_type: Option type (CALL or PUT)
            
        Returns:
            Formatted option symbol
        """
        # Parse the expiration date
        exp_date = datetime.strptime(expiration_date, '%Y-%m-%d')
        
        # Format the option symbol
        # Note: This is a simplified version - actual format may vary by broker
        # Format: Symbol_YYMMDD_Strike_Type
        # Example: AAPL_240621_150_C
        formatted_symbol = f"{symbol}_{exp_date.strftime('%y%m%d')}_{int(strike_price)}_{option_type[0]}"
        
        return formatted_symbol
    
    def _is_option_order(self, order: Dict[str, Any]) -> bool:
        """
        Check if an order is an option order.
        
        Args:
            order: Order data dictionary
            
        Returns:
            True if it's an option order, False otherwise
        """
        # Check if orderLegCollection exists and has at least one leg
        if 'orderLegCollection' not in order or not order['orderLegCollection']:
            return False
        
        # Check the first leg's instrument type
        first_leg = order['orderLegCollection'][0]
        if 'instrument' not in first_leg:
            return False
        
        # Check if assetType is OPTION
        return first_leg['instrument'].get('assetType') == 'OPTION'

# Create a singleton instance
option_orders_service = OptionOrdersService()