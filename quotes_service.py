#!/usr/bin/env python3
"""
Quotes Service Module for Schwab API Client-Server System.
Handles stock quote requests using the schwabdev library.
"""
import logging
from typing import Dict, List, Union, Any, Optional
from state_manager import state_manager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('quotes_service')

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
    
    def get_quotes(self, symbols: Optional[Union[List[str], str]] = None,
                  fields: Optional[str] = "all", 
                  indicative: bool = False) -> Dict[str, Any]:
        """
        Get quotes for specified symbols. If no symbols are provided,
        it defaults to the last requested symbols or 'SPY'.
        
        Args:
            symbols: Optional list/string of symbols.
            fields: Fields to include ("all", "quote", "fundamental").
            indicative: Whether to return indicative quotes.
            
        Returns:
            Dictionary with quote results or error information.
        """
        if not self.schwab_client:
            return {"success": False, "error": "Schwab client not initialized."}
        
        try:
            # Defaulting logic
            if not symbols:
                last_request = state_manager.get_last_stock_quote_request()
                if last_request and 'symbols' in last_request:
                    symbols = last_request['symbols']
                    logger.info(f"No symbols provided. Defaulting to last request: {symbols}")
                else:
                    symbols = ['SPY']
                    logger.info("No symbols provided and no state found. Defaulting to 'SPY'.")

            logger.info(f"Requesting quotes for symbols: {symbols}")
            
            # Convert string to list if needed
            if isinstance(symbols, str) and ',' in symbols:
                symbols = [s.strip() for s in symbols.split(',')]
            elif isinstance(symbols, str):
                symbols = [symbols]
                
            if fields not in ["all", "quote", "fundamental"]:
                logger.warning(f"Invalid fields parameter: {fields}. Using default 'all'.")
                fields = "all"
            
            quotes_response = self.schwab_client.quotes(
                symbols=symbols,
                fields=fields,
                indicative=indicative
            )
            
            if hasattr(quotes_response, 'json'):
                quotes_data = quotes_response.json()
                logger.info(f"Successfully retrieved quotes for {len(symbols)} symbols")

                # Save the successful request to state
                state_manager.save_stock_quote_request({'symbols': symbols})

                # Format the quotes into the specified string format
                formatted_quotes = []
                for symbol, details in quotes_data.items():
                    quote = details.get('quote', {})

                    formatted_string = (
                        f"{quote.get('symbol', symbol)} "
                        f"{quote.get('lastPrice', 'N/A')} "
                        f"{quote.get('bidPrice', 'N/A')} "
                        f"{quote.get('askPrice', 'N/A')} "
                        f"{quote.get('totalVolume', 'N/A')}"
                    )
                    formatted_quotes.append(formatted_string)

                return {"success": True, "data": formatted_quotes}
            else:
                logger.warning("Response object does not have a 'json' method. Returning raw data.")
                return {"success": True, "data": quotes_response}
                
        except Exception as e:
            logger.error(f"Error getting quotes: {str(e)}")
            return {"success": False, "error": f"Failed to get quotes: {str(e)}"}
    
    def validate_quote_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate a quote request. Symbols are now optional.
        """
        validated_params = {}

        if 'symbols' in request_data and request_data['symbols']:
            validated_params['symbols'] = request_data['symbols']
        else:
            validated_params['symbols'] = None # Explicitly set to None if missing/empty

        validated_params['fields'] = request_data.get('fields', 'all')
        indicative = request_data.get('indicative', False)
        
        if isinstance(indicative, str):
            indicative = indicative.lower() == 'true'
        validated_params['indicative'] = indicative
            
        if validated_params['fields'] not in ["all", "quote", "fundamental"]:
            return {
                "success": False,
                "error": f"Invalid fields parameter: {validated_params['fields']}. Valid options are 'all', 'quote', or 'fundamental'."
            }
            
        return {"success": True, "validated_params": validated_params}

# Create a singleton instance
quotes_service = QuotesService()