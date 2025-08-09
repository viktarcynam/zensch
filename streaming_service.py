#!/usr/bin/env python3
"""
Streaming Service Module for Schwab API Client-Server System.
Handles real-time data streaming for stocks and options with subscription limits.

Subscription Limits:
- Maximum 1 stock symbol subscription (new requests replace existing)
- Maximum 4 option subscriptions (2 strikes × 2 types: CALL/PUT)
- Option subscriptions are for 1 underlying symbol at a specified expiry date
- All subscriptions provide bid, ask, and volume data
"""
import logging
import threading
import time
from typing import Dict, Any, List, Set
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('streaming_service')

class StreamingService:
    """Service for handling real-time data streaming."""
    
    # Streaming limits
    MAX_STOCK_SUBSCRIPTIONS = 1
    MAX_OPTION_SUBSCRIPTIONS = 4
    
    def __init__(self, schwab_client=None):
        """
        Initialize the streaming service.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
        """
        self.schwab_client = schwab_client
        self.streaming_session = None
        self.streaming_thread = None
        self.is_streaming = False
        self.stock_subscriptions = set()  # Set of stock symbols subscribed to (max 1)
        self.option_subscriptions = set()  # Set of option symbols subscribed to (max 4)
        
        # In-memory storage for streamed data
        self.stock_data = {}  # Format: {symbol: {price, bid, ask, volume, timestamp}}
        self.option_data = {}  # Format: {symbol: {underlying_price, bid, ask, volume, timestamp}}
        
        # Lock for thread-safe access to data
        self.data_lock = threading.Lock()
        
        logger.info("Streaming service initialized")
    
    def get_subscription_status(self) -> Dict[str, Any]:
        """
        Get the current subscription status and limits.
        
        Returns:
            Dictionary with subscription information
        """
        with self.data_lock:
            return {
                "success": True,
                "is_streaming": self.is_streaming,
                "limits": {
                    "max_stocks": self.MAX_STOCK_SUBSCRIPTIONS,
                    "max_options": self.MAX_OPTION_SUBSCRIPTIONS
                },
                "current_subscriptions": {
                    "stocks": list(self.stock_subscriptions),
                    "options": list(self.option_subscriptions)
                },
                "subscription_counts": {
                    "stocks": len(self.stock_subscriptions),
                    "options": len(self.option_subscriptions)
                },
                "data_available": {
                    "stocks": list(self.stock_data.keys()),
                    "options": list(self.option_data.keys())
                }
            }
    
    def set_client(self, schwab_client):
        """
        Set the schwabdev client instance.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
        """
        self.schwab_client = schwab_client
        logger.info("Schwab client set in streaming service")
    
    def start_streaming(self):
        """
        Start the streaming session if not already running.
        
        Returns:
            Dictionary with success/error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in streaming service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        if self.is_streaming:
            logger.info("Streaming session already running")
            return {
                "success": True,
                "message": "Streaming session already running"
            }
        
        try:
            logger.info("Starting streaming session")
            
            # Use the schwabdev stream object
            self.streaming_session = self.schwab_client.stream
            
            # Start the streaming with our custom receiver function
            self.streaming_session.start(receiver=self._process_streaming_message, daemon=True)
            
            # Set streaming flag
            self.is_streaming = True
            
            # Schedule subscription updates in a separate thread to avoid blocking
            import threading
            def delayed_subscription_update():
                time.sleep(2)  # Allow stream to initialize
                self._update_subscriptions()
            
            threading.Thread(target=delayed_subscription_update, daemon=True).start()
            
            logger.info("Streaming session started successfully")
            return {
                "success": True,
                "message": "Streaming session started successfully"
            }
        except Exception as e:
            logger.error(f"Error starting streaming session: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to start streaming session: {str(e)}"
            }
    
    def stop_streaming(self):
        """
        Stop the streaming session if running.
        
        Returns:
            Dictionary with success/error information
        """
        if not self.is_streaming:
            logger.info("No streaming session running")
            return {
                "success": True,
                "message": "No streaming session running"
            }
        
        try:
            logger.info("Stopping streaming session")
            
            # Set flag to stop streaming
            self.is_streaming = False
            
            # Stop the schwabdev stream
            if self.streaming_session:
                self.streaming_session.stop()
                self.streaming_session = None
            
            logger.info("Streaming session stopped successfully")
            return {
                "success": True,
                "message": "Streaming session stopped successfully"
            }
        except Exception as e:
            logger.error(f"Error stopping streaming session: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to stop streaming session: {str(e)}"
            }
    
    def add_stock_subscription(self, symbol: str) -> Dict[str, Any]:
        """
        Add a stock symbol to the streaming subscription.
        Replaces existing stock subscription since limit is 1.
        
        Args:
            symbol: Stock symbol to subscribe to
            
        Returns:
            Dictionary with success/error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in streaming service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Adding stock subscription for {symbol}")
            
            # Replace existing stock subscription (limit is 1)
            with self.data_lock:
                old_subscriptions = self.stock_subscriptions.copy()
                self.stock_subscriptions.clear()
                self.stock_subscriptions.add(symbol)
                
                # Clear old stock data
                for old_symbol in old_subscriptions:
                    if old_symbol != symbol and old_symbol in self.stock_data:
                        del self.stock_data[old_symbol]
                        logger.info(f"Removed old stock data for {old_symbol}")
            
            # Start streaming if not already running
            if not self.is_streaming:
                self.start_streaming()
            else:
                # Update subscriptions in the streaming session (non-blocking)
                import threading
                threading.Thread(target=self._update_subscriptions, daemon=True).start()
            
            if old_subscriptions and symbol not in old_subscriptions:
                logger.info(f"Replaced stock subscription {old_subscriptions} with {symbol}")
            else:
                logger.info(f"Stock subscription for {symbol} added successfully")
            
            return {
                "success": True,
                "message": f"Stock subscription for {symbol} added successfully"
            }
        except Exception as e:
            logger.error(f"Error adding stock subscription: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to add stock subscription: {str(e)}"
            }
    
    def add_option_subscriptions(self, symbol: str, expiration_date: str, 
                                strike_prices: List[float]) -> Dict[str, Any]:
        """
        Add option subscriptions for a specific underlying symbol and expiration.
        Subscribes to both CALL and PUT for each strike price (max 4 total options).
        Replaces all existing option subscriptions.
        
        Args:
            symbol: Underlying stock symbol
            expiration_date: Option expiration date in format YYYY-MM-DD
            strike_prices: List of strike prices (max 2)
            
        Returns:
            Dictionary with success/error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in streaming service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        if len(strike_prices) > 2:
            return {
                "success": False,
                "error": "Maximum 2 strike prices allowed (4 total options: 2 calls + 2 puts)"
            }
        
        try:
            logger.info(f"Adding option subscriptions for {symbol} expiry {expiration_date} strikes {strike_prices}")
            
            # Format the option symbols
            from option_orders_service import OptionOrdersService
            new_option_symbols = set()
            
            for strike_price in strike_prices:
                # Add CALL option
                call_symbol = OptionOrdersService._format_option_symbol(
                    None, symbol, expiration_date, strike_price, "CALL"
                )
                new_option_symbols.add(call_symbol)
                
                # Add PUT option
                put_symbol = OptionOrdersService._format_option_symbol(
                    None, symbol, expiration_date, strike_price, "PUT"
                )
                new_option_symbols.add(put_symbol)
            
            # Replace existing option subscriptions (limit is 4)
            with self.data_lock:
                old_subscriptions = self.option_subscriptions.copy()
                self.option_subscriptions.clear()
                self.option_subscriptions.update(new_option_symbols)
                
                # Clear old option data
                for old_symbol in old_subscriptions:
                    if old_symbol not in new_option_symbols and old_symbol in self.option_data:
                        del self.option_data[old_symbol]
                        logger.info(f"Removed old option data for {old_symbol}")
            
            # Start streaming if not already running
            if not self.is_streaming:
                self.start_streaming()
            else:
                # Update subscriptions in the streaming session (non-blocking)
                import threading
                threading.Thread(target=self._update_subscriptions, daemon=True).start()
            
            if old_subscriptions:
                logger.info(f"Replaced option subscriptions with {len(new_option_symbols)} new options")
            else:
                logger.info(f"Added {len(new_option_symbols)} option subscriptions")
            
            return {
                "success": True,
                "message": f"Added {len(new_option_symbols)} option subscriptions for {symbol}",
                "option_symbols": list(new_option_symbols)
            }
        except Exception as e:
            logger.error(f"Error adding option subscriptions: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to add option subscriptions: {str(e)}"
            }
    
    def add_option_subscription(self, symbol: str, option_type: str, 
                               expiration_date: str, strike_price: float) -> Dict[str, Any]:
        """
        Add a single option to the streaming subscription.
        This method is deprecated - use add_option_subscriptions instead.
        
        Args:
            symbol: Underlying stock symbol
            option_type: Option type (CALL or PUT)
            expiration_date: Option expiration date in format YYYY-MM-DD
            strike_price: Option strike price
            
        Returns:
            Dictionary with success/error information
        """
        logger.warning("add_option_subscription is deprecated. Use add_option_subscriptions instead.")
        return self.add_option_subscriptions(symbol, expiration_date, [strike_price])
    
    def get_stock_data(self, symbol: str) -> Dict[str, Any]:
        """
        Get the latest streamed data for a stock.
        
        Args:
            symbol: Stock symbol
            
        Returns:
            Dictionary with stock data or error information
        """
        with self.data_lock:
            if symbol not in self.stock_data:
                # If not in streaming data, add subscription and return current quote
                self.add_stock_subscription(symbol)
                
                try:
                    # Get current quote
                    quote_response = self.schwab_client.get_quote(symbol)
                    if hasattr(quote_response, 'json'):
                        quote_data = quote_response.json()
                        
                        # Extract relevant data
                        stock_data = {
                            'price': quote_data.get('lastPrice'),
                            'bid': quote_data.get('bidPrice'),
                            'ask': quote_data.get('askPrice'),
                            'volume': quote_data.get('totalVolume'),
                            'timestamp': datetime.now().isoformat(),
                            'source': 'quote'  # Indicate this is from a quote, not streaming
                        }
                        
                        # Store in streaming data
                        self.stock_data[symbol] = stock_data
                        
                        return {
                            "success": True,
                            "data": stock_data,
                            "message": f"Stock data for {symbol} retrieved from quote (streaming subscription added)"
                        }
                    else:
                        return {
                            "success": False,
                            "error": f"Failed to get quote for {symbol}"
                        }
                except Exception as e:
                    logger.error(f"Error getting quote: {str(e)}")
                    return {
                        "success": False,
                        "error": f"Failed to get quote: {str(e)}"
                    }
            else:
                # Return the cached streaming data
                return {
                    "success": True,
                    "data": self.stock_data[symbol],
                    "message": f"Stock data for {symbol} retrieved from streaming cache"
                }
    
    def get_option_data(self, symbol: str, option_type: str, 
                       expiration_date: str, strike_price: float) -> Dict[str, Any]:
        """
        Get the latest streamed data for an option.
        
        Args:
            symbol: Underlying stock symbol
            option_type: Option type (CALL or PUT)
            expiration_date: Option expiration date in format YYYY-MM-DD
            strike_price: Option strike price
            
        Returns:
            Dictionary with option data or error information
        """
        # Format the option symbol
        from option_orders_service import OptionOrdersService
        option_symbol = OptionOrdersService._format_option_symbol(
            None, symbol, expiration_date, strike_price, option_type
        )
        
        with self.data_lock:
            if option_symbol not in self.option_data:
                # If not in streaming data, add subscription and return current option chain
                self.add_option_subscription(symbol, option_type, expiration_date, strike_price)
                
                try:
                    # Get current option chain
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
                        option_contract = None
                        
                        # Navigate through the option chain structure to find the contract
                        if 'callExpDateMap' in chain_data and option_type == "CALL":
                            for date_key, strikes in chain_data['callExpDateMap'].items():
                                if str(strike_price) in strikes:
                                    option_contract = strikes[str(strike_price)][0]
                                    break
                        
                        elif 'putExpDateMap' in chain_data and option_type == "PUT":
                            for date_key, strikes in chain_data['putExpDateMap'].items():
                                if str(strike_price) in strikes:
                                    option_contract = strikes[str(strike_price)][0]
                                    break
                        
                        if option_contract:
                            # Get underlying stock price
                            underlying_price = None
                            try:
                                quote_response = self.schwab_client.get_quote(symbol)
                                if hasattr(quote_response, 'json'):
                                    quote_data = quote_response.json()
                                    underlying_price = quote_data.get('lastPrice')
                            except Exception as quote_error:
                                logger.warning(f"Error getting underlying stock price: {str(quote_error)}")
                            
                            # Extract relevant data
                            option_data = {
                                'underlying_price': underlying_price,
                                'bid': option_contract.get('bid'),
                                'ask': option_contract.get('ask'),
                                'volume': option_contract.get('totalVolume'),
                                'timestamp': datetime.now().isoformat(),
                                'source': 'quote'  # Indicate this is from a quote, not streaming
                            }
                            
                            # Store in streaming data
                            self.option_data[option_symbol] = option_data
                            
                            return {
                                "success": True,
                                "data": option_data,
                                "message": f"Option data for {option_symbol} retrieved from option chain (streaming subscription added)"
                            }
                        else:
                            return {
                                "success": False,
                                "error": f"Option contract not found in chain for {option_symbol}"
                            }
                    else:
                        return {
                            "success": False,
                            "error": f"Failed to get option chain for {option_symbol}"
                        }
                except Exception as e:
                    logger.error(f"Error getting option chain: {str(e)}")
                    return {
                        "success": False,
                        "error": f"Failed to get option chain: {str(e)}"
                    }
            else:
                # Return the cached streaming data
                return {
                    "success": True,
                    "data": self.option_data[option_symbol],
                    "message": f"Option data for {option_symbol} retrieved from streaming cache"
                }
    
    def _streaming_worker(self):
        """Worker thread function for handling streaming data - not used with schwabdev."""
        # This method is no longer used since schwabdev handles threading internally
        # The _process_streaming_message method is called directly by schwabdev's stream
        pass
    
    def _update_subscriptions(self):
        """Update the streaming subscriptions based on current subscription sets."""
        if not self.streaming_session:
            logger.warning("Cannot update subscriptions: No streaming session")
            return
        
        try:
            with self.data_lock:
                # First, unsubscribe from all existing subscriptions to clear the slate
                # This ensures we only have the limited subscriptions we want
                if hasattr(self.streaming_session, 'subscriptions') and self.streaming_session.subscriptions:
                    logger.info("Clearing all existing subscriptions")
                    
                    # Unsubscribe from existing equity subscriptions
                    if 'LEVELONE_EQUITIES' in self.streaming_session.subscriptions:
                        existing_equity_keys = list(self.streaming_session.subscriptions['LEVELONE_EQUITIES'].keys())
                        if existing_equity_keys:
                            unsub_request = self.streaming_session.level_one_equities(
                                keys=existing_equity_keys,
                                fields="0,1,2,3",  # Minimal fields for unsubscribe
                                command="UNSUBS"
                            )
                            self.streaming_session.send(unsub_request)
                            logger.info(f"Unsubscribed from {len(existing_equity_keys)} equity symbols")
                    
                    # Unsubscribe from existing option subscriptions
                    if 'LEVELONE_OPTIONS' in self.streaming_session.subscriptions:
                        existing_option_keys = list(self.streaming_session.subscriptions['LEVELONE_OPTIONS'].keys())
                        if existing_option_keys:
                            unsub_request = self.streaming_session.level_one_options(
                                keys=existing_option_keys,
                                fields="0,1,2,3",  # Minimal fields for unsubscribe
                                command="UNSUBS"
                            )
                            self.streaming_session.send(unsub_request)
                            logger.info(f"Unsubscribed from {len(existing_option_keys)} option symbols")
                
                # Now subscribe to the current limited set
                # Subscribe to Level 1 Equity quotes for stocks (max 1)
                if self.stock_subscriptions:
                    logger.info(f"Subscribing to Level 1 Equity quotes for {len(self.stock_subscriptions)} symbols")
                    # Use essential fields for bid, ask, last price, volume
                    request = self.streaming_session.level_one_equities(
                        keys=list(self.stock_subscriptions),
                        fields="0,1,2,3,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31",
                        command="ADD"
                    )
                    self.streaming_session.send(request)
                
                # Subscribe to Level 1 Option quotes for options (max 4)
                if self.option_subscriptions:
                    logger.info(f"Subscribing to Level 1 Option quotes for {len(self.option_subscriptions)} symbols")
                    # Use essential fields for bid, ask, volume, underlying price
                    request = self.streaming_session.level_one_options(
                        keys=list(self.option_subscriptions),
                        fields="0,1,2,3,8,9,10,11,12,13,14,15,16,17,18,19,20,21,22,23,24,25,26,27,28,29,30,31",
                        command="ADD"
                    )
                    self.streaming_session.send(request)
                    
                logger.info(f"Updated subscriptions: {len(self.stock_subscriptions)} stocks, {len(self.option_subscriptions)} options")
                
        except Exception as e:
            logger.error(f"Error updating subscriptions: {str(e)}")
    
    def _process_streaming_message(self, message):
        """
        Process a streaming message and update the in-memory data.
        
        Args:
            message: Streaming message from the Schwab API (JSON string)
        """
        try:
            # Parse the JSON message if it's a string
            if isinstance(message, str):
                import json
                data = json.loads(message)
            else:
                data = message
            
            # Check if this is a response with data
            if 'data' in data:
                for item in data['data']:
                    service = item.get('service')
                    
                    if service == 'LEVELONE_EQUITIES':
                        # Process stock quote update
                        self._process_stock_update(item)
                    elif service == 'LEVELONE_OPTIONS':
                        # Process option quote update
                        self._process_option_update(item)
            
            # Log the message for debugging (first 200 chars)
            logger.debug(f"Received streaming message: {str(message)[:200]}...")
            
        except Exception as e:
            logger.error(f"Error processing streaming message: {str(e)}")
            logger.debug(f"Message content: {str(message)[:500]}...")
    
    def _process_stock_update(self, message):
        """
        Process a stock quote update message.
        
        Args:
            message: Stock quote update message
        """
        try:
            # Extract content data - schwabdev format
            content = message.get('content', [])
            
            for item in content:
                symbol = item.get('key')
                if symbol:
                    with self.data_lock:
                        # Update or create stock data entry
                        self.stock_data[symbol] = {
                            'price': item.get('1'),  # Last price
                            'bid': item.get('2'),    # Bid price
                            'ask': item.get('3'),    # Ask price
                            'volume': item.get('8'), # Volume
                            'timestamp': datetime.now().isoformat(),
                            'source': 'streaming'
                        }
                        
                        logger.debug(f"Updated streaming data for stock {symbol}")
        except Exception as e:
            logger.error(f"Error processing stock update: {str(e)}")
            logger.debug(f"Message: {message}")
    
    def _process_option_update(self, message):
        """
        Process an option quote update message.
        
        Args:
            message: Option quote update message
        """
        try:
            # Extract content data - schwabdev format
            content = message.get('content', [])
            
            for item in content:
                option_symbol = item.get('key')
                if option_symbol:
                    with self.data_lock:
                        # Update or create option data entry
                        self.option_data[option_symbol] = {
                            'underlying_price': item.get('10'),  # Underlying price
                            'bid': item.get('1'),               # Bid price
                            'ask': item.get('2'),               # Ask price
                            'volume': item.get('8'),            # Volume
                            'timestamp': datetime.now().isoformat(),
                            'source': 'streaming'
                        }
                        
                        logger.debug(f"Updated streaming data for option {option_symbol}")
        except Exception as e:
            logger.error(f"Error processing option update: {str(e)}")
            logger.debug(f"Message: {message}")

# Create a singleton instance
streaming_service = StreamingService()