#!/usr/bin/env python3
"""
Streaming Service Module for Schwab API Client-Server System.
Handles real-time data streaming for stocks and options.
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
        self.stock_subscriptions = set()  # Set of stock symbols subscribed to
        self.option_subscriptions = set()  # Set of option symbols subscribed to
        
        # In-memory storage for streamed data
        self.stock_data = {}  # Format: {symbol: {price, bid, ask, volume, timestamp}}
        self.option_data = {}  # Format: {symbol: {underlying_price, bid, ask, volume, timestamp}}
        
        # Lock for thread-safe access to data
        self.data_lock = threading.Lock()
        
        logger.info("Streaming service initialized")
    
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
            
            # Create a streaming session
            self.streaming_session = self.schwab_client.create_streaming_session()
            
            # Start the streaming thread
            self.is_streaming = True
            self.streaming_thread = threading.Thread(target=self._streaming_worker)
            self.streaming_thread.daemon = True
            self.streaming_thread.start()
            
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
            
            # Set flag to stop the streaming thread
            self.is_streaming = False
            
            # Wait for the thread to terminate
            if self.streaming_thread and self.streaming_thread.is_alive():
                self.streaming_thread.join(timeout=5.0)
            
            # Close the streaming session
            if self.streaming_session:
                self.streaming_session.close()
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
            
            # Add to subscription set
            with self.data_lock:
                self.stock_subscriptions.add(symbol)
            
            # Start streaming if not already running
            if not self.is_streaming:
                self.start_streaming()
            else:
                # Update subscriptions in the streaming session
                self._update_subscriptions()
            
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
    
    def add_option_subscription(self, symbol: str, option_type: str, 
                               expiration_date: str, strike_price: float) -> Dict[str, Any]:
        """
        Add an option to the streaming subscription.
        
        Args:
            symbol: Underlying stock symbol
            option_type: Option type (CALL or PUT)
            expiration_date: Option expiration date in format YYYY-MM-DD
            strike_price: Option strike price
            
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
            # Format the option symbol
            from option_orders_service import OptionOrdersService
            option_symbol = OptionOrdersService._format_option_symbol(
                None, symbol, expiration_date, strike_price, option_type
            )
            
            logger.info(f"Adding option subscription for {option_symbol}")
            
            # Add to subscription set
            with self.data_lock:
                self.option_subscriptions.add(option_symbol)
                # Also subscribe to the underlying stock
                self.stock_subscriptions.add(symbol)
            
            # Start streaming if not already running
            if not self.is_streaming:
                self.start_streaming()
            else:
                # Update subscriptions in the streaming session
                self._update_subscriptions()
            
            logger.info(f"Option subscription for {option_symbol} added successfully")
            return {
                "success": True,
                "message": f"Option subscription for {option_symbol} added successfully"
            }
        except Exception as e:
            logger.error(f"Error adding option subscription: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to add option subscription: {str(e)}"
            }
    
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
        """Worker thread function for handling streaming data."""
        logger.info("Streaming worker thread started")
        
        try:
            # Initial subscription setup
            self._update_subscriptions()
            
            # Main streaming loop
            while self.is_streaming:
                try:
                    # Process streaming messages
                    message = self.streaming_session.receive_message(timeout=1.0)
                    
                    if message:
                        self._process_streaming_message(message)
                except Exception as e:
                    logger.error(f"Error in streaming loop: {str(e)}")
                    time.sleep(1.0)  # Avoid tight loop on error
        except Exception as e:
            logger.error(f"Streaming worker thread error: {str(e)}")
        finally:
            logger.info("Streaming worker thread stopped")
    
    def _update_subscriptions(self):
        """Update the streaming subscriptions based on current subscription sets."""
        if not self.streaming_session:
            logger.warning("Cannot update subscriptions: No streaming session")
            return
        
        try:
            with self.data_lock:
                # Subscribe to Level 1 Equity quotes for stocks
                if self.stock_subscriptions:
                    logger.info(f"Subscribing to Level 1 Equity quotes for {len(self.stock_subscriptions)} symbols")
                    self.streaming_session.subscribe_level_1_equities(list(self.stock_subscriptions))
                
                # Subscribe to Level 1 Option quotes for options
                if self.option_subscriptions:
                    logger.info(f"Subscribing to Level 1 Option quotes for {len(self.option_subscriptions)} symbols")
                    self.streaming_session.subscribe_level_1_options(list(self.option_subscriptions))
        except Exception as e:
            logger.error(f"Error updating subscriptions: {str(e)}")
    
    def _process_streaming_message(self, message):
        """
        Process a streaming message and update the in-memory data.
        
        Args:
            message: Streaming message from the Schwab API
        """
        try:
            # Extract message type and data
            message_type = message.get('service')
            
            if message_type == 'LEVELONE_EQUITIES':
                # Process stock quote update
                self._process_stock_update(message)
            elif message_type == 'LEVELONE_OPTIONS':
                # Process option quote update
                self._process_option_update(message)
        except Exception as e:
            logger.error(f"Error processing streaming message: {str(e)}")
    
    def _process_stock_update(self, message):
        """
        Process a stock quote update message.
        
        Args:
            message: Stock quote update message
        """
        try:
            # Extract symbol and data
            symbol = message.get('key')
            content = message.get('content', [{}])[0]
            
            if symbol and content:
                with self.data_lock:
                    # Update or create stock data entry
                    self.stock_data[symbol] = {
                        'price': content.get('LAST_PRICE'),
                        'bid': content.get('BID_PRICE'),
                        'ask': content.get('ASK_PRICE'),
                        'volume': content.get('VOLUME'),
                        'timestamp': datetime.now().isoformat(),
                        'source': 'streaming'
                    }
                    
                    logger.debug(f"Updated streaming data for stock {symbol}")
        except Exception as e:
            logger.error(f"Error processing stock update: {str(e)}")
    
    def _process_option_update(self, message):
        """
        Process an option quote update message.
        
        Args:
            message: Option quote update message
        """
        try:
            # Extract symbol and data
            option_symbol = message.get('key')
            content = message.get('content', [{}])[0]
            
            if option_symbol and content:
                with self.data_lock:
                    # Update or create option data entry
                    self.option_data[option_symbol] = {
                        'underlying_price': content.get('UNDERLYING_PRICE'),
                        'bid': content.get('BID_PRICE'),
                        'ask': content.get('ASK_PRICE'),
                        'volume': content.get('VOLUME'),
                        'timestamp': datetime.now().isoformat(),
                        'source': 'streaming'
                    }
                    
                    logger.debug(f"Updated streaming data for option {option_symbol}")
        except Exception as e:
            logger.error(f"Error processing option update: {str(e)}")

# Create a singleton instance
streaming_service = StreamingService()