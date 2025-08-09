#!/usr/bin/env python3
"""
Options Service Module for Schwab API Client-Server System.
Handles stock options chain requests using the schwabdev library.
"""
import logging
from typing import Dict, List, Union, Any, Optional
from datetime import datetime

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('options_service')

# Import streaming service for real-time data
from streaming_service import streaming_service

# Valid parameter values for validation
VALID_CONTRACT_TYPES = ["ALL", "CALL", "PUT"]
VALID_STRATEGIES = ["SINGLE", "ANALYTICAL", "COVERED", "VERTICAL", "CALENDAR", 
                    "STRANGLE", "STRADDLE", "BUTTERFLY", "CONDOR", "DIAGONAL", 
                    "COLLAR", "ROLL"]
VALID_RANGES = ["ITM", "NTM", "OTM", "SAK", "SBK", "SNK", "ALL"]
VALID_EXP_MONTHS = ["JAN", "FEB", "MAR", "APR", "MAY", "JUN", 
                    "JUL", "AUG", "SEP", "OCT", "NOV", "DEC"]
VALID_ENTITLEMENTS = ["PN", "NP", "PP"]

class OptionsService:
    """Service for handling stock options chain requests."""
    
    def __init__(self, schwab_client=None):
        """
        Initialize the options service.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
        """
        self.schwab_client = schwab_client
        logger.info("Options service initialized")
    
    def set_client(self, schwab_client):
        """
        Set the schwabdev client instance.
        
        Args:
            schwab_client: Authenticated schwabdev client instance
        """
        self.schwab_client = schwab_client
        logger.info("Schwab client set in options service")
    
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
            Dictionary with option chain results or error information
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in options service")
            return {
                "success": False,
                "error": "Schwab client not initialized. Please initialize credentials first."
            }
        
        try:
            logger.info(f"Requesting option chains for symbol: {symbol}")
            
            # Process date parameters if they are strings
            if 'fromDate' in kwargs and isinstance(kwargs['fromDate'], str):
                try:
                    # Convert string date to datetime object if in yyyy-MM-dd format
                    kwargs['fromDate'] = datetime.strptime(kwargs['fromDate'], '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Invalid fromDate format: {kwargs['fromDate']}. Should be yyyy-MM-dd.")
            
            if 'toDate' in kwargs and isinstance(kwargs['toDate'], str):
                try:
                    # Convert string date to datetime object if in yyyy-MM-dd format
                    kwargs['toDate'] = datetime.strptime(kwargs['toDate'], '%Y-%m-%d')
                except ValueError:
                    logger.warning(f"Invalid toDate format: {kwargs['toDate']}. Should be yyyy-MM-dd.")
            
            # Convert string booleans to actual booleans
            if 'includeUnderlyingQuote' in kwargs and isinstance(kwargs['includeUnderlyingQuote'], str):
                kwargs['includeUnderlyingQuote'] = kwargs['includeUnderlyingQuote'].lower() == 'true'
            
            # Convert numeric strings to appropriate types
            numeric_params = ['strikeCount', 'interval', 'strike', 'volatility', 
                             'underlyingPrice', 'interestRate', 'daysToExpiration']
            
            for param in numeric_params:
                if param in kwargs and isinstance(kwargs[param], str):
                    try:
                        if '.' in kwargs[param]:
                            kwargs[param] = float(kwargs[param])
                        else:
                            kwargs[param] = int(kwargs[param])
                    except ValueError:
                        logger.warning(f"Invalid {param} value: {kwargs[param]}. Should be numeric.")
            
            # Extract use_streaming parameter and remove from kwargs if present
            use_streaming = kwargs.pop('use_streaming', False)
            
            # Always add underlying stock to streaming subscriptions for future use
            streaming_service.add_stock_subscription(symbol)
            logger.info(f"Added underlying stock {symbol} to streaming subscriptions")
            
            # Check if we should use streaming data for a specific option
            if (use_streaming and 
                'contractType' in kwargs and kwargs['contractType'] in ['CALL', 'PUT'] and
                'strike' in kwargs and
                ('fromDate' in kwargs or 'toDate' in kwargs)):
                
                # Try to get streaming data for this specific option
                option_type = kwargs['contractType']
                strike_price = float(kwargs['strike'])
                expiration_date = kwargs.get('fromDate') or kwargs.get('toDate')
                
                if expiration_date:
                    # Add option to streaming subscriptions
                    streaming_service.add_option_subscription(
                        symbol, option_type, expiration_date, strike_price
                    )
                    logger.info(f"Added option {symbol} {option_type} {strike_price} {expiration_date} to streaming subscriptions")
                    
                    # Try to get streaming data if requested
                    streaming_data = streaming_service.get_option_data(
                        symbol, option_type, expiration_date, strike_price
                    )
                    
                    if streaming_data.get('success') and streaming_data.get('data', {}).get('source') == 'streaming':
                        logger.info(f"Using streaming data for option {symbol} {option_type} {strike_price} {expiration_date}")
                        return streaming_data
                    else:
                        logger.info(f"Streaming data not available for option, using option chain API")
            
            # Call schwabdev option_chains method
            options_response = self.schwab_client.option_chains(symbol=symbol, **kwargs)
            
            # Process the response
            if hasattr(options_response, 'json'):
                options_data = options_response.json()
                logger.info(f"Successfully retrieved option chains for {symbol}")
                
                # If specific contract type and strike are requested, add to streaming for future use
                if 'contractType' in kwargs and kwargs['contractType'] in ['CALL', 'PUT']:
                    # Extract expiration dates and strikes from the response
                    if kwargs['contractType'] == 'CALL' and 'callExpDateMap' in options_data:
                        for exp_date, strikes in options_data['callExpDateMap'].items():
                            # Extract expiration date from the key (format varies by broker)
                            exp_date_parts = exp_date.split(':')[0]  # Remove any extra parts after colon
                            
                            for strike in strikes.keys():
                                # Add each option to streaming
                                streaming_service.add_option_subscription(
                                    symbol, 'CALL', exp_date_parts, float(strike)
                                )
                                logger.debug(f"Added option {symbol} CALL {strike} {exp_date_parts} to streaming subscriptions")
                    
                    elif kwargs['contractType'] == 'PUT' and 'putExpDateMap' in options_data:
                        for exp_date, strikes in options_data['putExpDateMap'].items():
                            # Extract expiration date from the key (format varies by broker)
                            exp_date_parts = exp_date.split(':')[0]  # Remove any extra parts after colon
                            
                            for strike in strikes.keys():
                                # Add each option to streaming
                                streaming_service.add_option_subscription(
                                    symbol, 'PUT', exp_date_parts, float(strike)
                                )
                                logger.debug(f"Added option {symbol} PUT {strike} {exp_date_parts} to streaming subscriptions")
                
                return {
                    "success": True,
                    "data": options_data
                }
            else:
                # Handle case where response is already parsed
                logger.info(f"Successfully retrieved option chains for {symbol}")
                return {
                    "success": True,
                    "data": options_response
                }
                
        except Exception as e:
            logger.error(f"Error getting option chains: {str(e)}")
            return {
                "success": False,
                "error": f"Failed to get option chains: {str(e)}"
            }
    
    def validate_option_chain_request(self, request_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Validate an option chain request.
        
        Args:
            request_data: Dictionary containing request parameters
            
        Returns:
            Dictionary with validation results
        """
        if 'symbol' not in request_data:
            return {
                "success": False,
                "error": "Missing required parameter: symbol"
            }
        
        # Create a copy of the request data for validation
        validated_params = {'symbol': request_data['symbol']}
        errors = []
        
        # Validate contractType
        if 'contractType' in request_data:
            if request_data['contractType'] in VALID_CONTRACT_TYPES:
                validated_params['contractType'] = request_data['contractType']
            else:
                errors.append(f"Invalid contractType: {request_data['contractType']}. "
                             f"Valid options are: {', '.join(VALID_CONTRACT_TYPES)}")
        
        # Validate strategy
        if 'strategy' in request_data:
            if request_data['strategy'] in VALID_STRATEGIES:
                validated_params['strategy'] = request_data['strategy']
            else:
                errors.append(f"Invalid strategy: {request_data['strategy']}. "
                             f"Valid options are: {', '.join(VALID_STRATEGIES)}")
        
        # Validate range
        if 'range' in request_data:
            if request_data['range'] in VALID_RANGES:
                validated_params['range'] = request_data['range']
            else:
                errors.append(f"Invalid range: {request_data['range']}. "
                             f"Valid options are: {', '.join(VALID_RANGES)}")
        
        # Validate expMonth
        if 'expMonth' in request_data:
            if request_data['expMonth'] in VALID_EXP_MONTHS:
                validated_params['expMonth'] = request_data['expMonth']
            else:
                errors.append(f"Invalid expMonth: {request_data['expMonth']}. "
                             f"Valid options are: {', '.join(VALID_EXP_MONTHS)}")
        
        # Validate entitlement
        if 'entitlement' in request_data:
            if request_data['entitlement'] in VALID_ENTITLEMENTS:
                validated_params['entitlement'] = request_data['entitlement']
            else:
                errors.append(f"Invalid entitlement: {request_data['entitlement']}. "
                             f"Valid options are: {', '.join(VALID_ENTITLEMENTS)}")
        
        # Validate date formats
        date_params = ['fromDate', 'toDate']
        for param in date_params:
            if param in request_data:
                if isinstance(request_data[param], str):
                    try:
                        # Just validate the format, don't convert yet
                        datetime.strptime(request_data[param], '%Y-%m-%d')
                        validated_params[param] = request_data[param]
                    except ValueError:
                        errors.append(f"Invalid {param} format: {request_data[param]}. "
                                     f"Should be in yyyy-MM-dd format.")
                else:
                    validated_params[param] = request_data[param]
        
        # Add other parameters without specific validation
        other_params = ['strikeCount', 'includeUnderlyingQuote', 'interval', 'strike',
                       'volatility', 'underlyingPrice', 'interestRate', 'daysToExpiration',
                       'optionType']
        
        for param in other_params:
            if param in request_data:
                validated_params[param] = request_data[param]
        
        # Add use_streaming parameter with default value
        use_streaming = request_data.get('use_streaming', False)
        if isinstance(use_streaming, str):
            use_streaming = use_streaming.lower() == 'true'
        validated_params['use_streaming'] = use_streaming
        
        if errors:
            return {
                "success": False,
                "error": "; ".join(errors)
            }
        
        return {
            "success": True,
            "validated_params": validated_params
        }

# Create a singleton instance
options_service = OptionsService()