#!/usr/bin/env python3
"""
Quotes Service Module for Schwab API Client-Server System.
Handles stock quote requests using the schwabdev library.
"""
import logging
from typing import Dict, List, Union, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('quotes_service')

# Import streaming service for real-time data
from streaming_service import streaming_service

class QuotesService:
    """Service for handling stock quote requests."""
    
    def __init__(self, schwab_client=None):
        """
        Initialize the quotes service.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
        """
        self.schwab_client = schwab_client
        logger.info("Quotes service initialized")
    
    def set_client(self, schwab_client):
        """
        Set the schwabdev client instance.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
        """
        self.schwab_client = schwab_client
        logger.info("Schwab client set in quotes service")
    
    def get_quotes(self, symbols: Union[List[str], str], 
                  fields: Optional[str] = "all", 
                  indicative: bool = False,
                  use_streaming: bool = False) -> Dict[str, Any]:
        """
        Get quotes for specified symbols.
        
        Args:
            symbols: List of symbols or comma-separated string of symbols
            fields: Fields to include in the quote ("all", "quote", or "fundamental")
            indicative: Whether to return indicative quotes
            use_streaming: Whether to use streaming data if available (default: False)
            
        Returns:
            Dictionary with quote results or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in quotes service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Requesting quotes for symbols: {symbols}")
            
            # Convert string to list if needed
            if isinstance(symbols, str) and ',' in symbols:
                symbols = [s.strip() for s in symbols.split(',')]
            elif isinstance(symbols, str):
                symbols = [symbols]
                
            # Validate fields parameter
            if fields not in ["all", "quote", "fundamental"]:
                logger.warning(f"Invalid fields parameter: {fields}. Using default 'all'.")
                fields = "all"
            
            # Always add symbols to streaming subscriptions for future use
            for symbol in symbols:
                streaming_service.add_stock_subscription(symbol)
                logger.info(f"Added {symbol} to streaming subscriptions")
            
            # Check if we should use streaming data
            if use_streaming and len(symbols) == 1:
                # For single symbol requests, try to get streaming data first
                streaming_data = streaming_service.get_stock_data(symbols[0])
                
                if streaming_data.get('success') and streaming_data.get('data', {}).get('source') == 'streaming':
                    logger.info(f"Using streaming data for {symbols[0]}")
                    return streaming_data
                else:
                    logger.info(f"Streaming data not available for {symbols[0]}, using quote API")
            
            # If streaming data not available or not requested, use regular quotes API
            quotes_response = self.schwab_client.quotes(
                symbols=symbols,
                fields=fields,
                indicative=indicative
            )
            
            # Process the response
            if hasattr(quotes_response, 'json'):
                quotes_data = quotes_response.json()
                logger.info(f"Successfully retrieved quotes for {len(symbols)} symbols")
                return {
                    "success": True,
                    "data": quotes_data
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully retrieved quotes for {len(symbols)} symbols")
                return {
                    "success": True,
                    "data": quotes_response
                }
                
        except Exception as e:
            logger.error(f"Error getting quotes: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get quotes: {str(e)}"
            }
    
    def validate_quote_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a quote request.
        
        Args:
            request_data: Dictionary containing request parameters
            
        Returns:
            Dictionary with validation results
        """
        if 'symbols' not in request_data:
            return {
                "success": False,
                "error": "Missing required parameter: symbols"
            }
            
        # Optional parameters with defaults
        fields = request_data.get('fields', 'all')
        indicative = request_data.get('indicative', False)
        use_streaming = request_data.get('use_streaming', False)
        
        # Convert string boolean to actual boolean if needed
        if isinstance(indicative, str):
            indicative = indicative.lower() == 'true'
        
        if isinstance(use_streaming, str):
            use_streaming = use_streaming.lower() == 'true'
            
        # Validate fields parameter
        if fields not in ["all", "quote", "fundamental"]:
            return {
                "success": False,
                "error": f"Invalid fields parameter: {fields}. Valid options are 'all', 'quote', or 'fundamental'."
            }
            
        return {
            "success": True,
            "validated_params": {
                "symbols": request_data['symbols'],
                "fields": fields,
                "indicative": indicative,
                "use_streaming": use_streaming
            }
        }

# Create a singleton instance
quotes_service = QuotesService()