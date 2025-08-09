#!/usr/bin/env python3
"""
Options Service Module for Schwab API Client-Server System.
Handles stock options chain requests using the schwabdev library.
"""
import logging
from typing import Dict, List, Union, Any, Optional
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('options_service')

# Import quotes_service to get underlying prices
from quotes_service import quotes_service
from state_manager import state_manager

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

    def _parse_expiry_date(self, expiry_input: Union[str, int]) -> Optional[datetime.date]:
        """
        Parse a flexible expiry date input into a date object.
        Supports yyyymmdd, mmdd, and dd formats.
        """
        today = datetime.now()
        s_expiry = str(expiry_input)

        try:
            if len(s_expiry) == 8 and s_expiry.isdigit():
                return datetime.strptime(s_expiry, '%Y%m%d').date()

            elif len(s_expiry) == 4 and s_expiry.isdigit():
                date_obj = datetime.strptime(s_expiry, '%m%d').date()
                date_obj = date_obj.replace(year=today.year)
                if date_obj < today.date():
                    date_obj = date_obj.replace(year=today.year + 1)
                return date_obj

            elif len(s_expiry) in [1, 2] and s_expiry.isdigit():
                day = int(s_expiry)
                if day < today.day:
                    # Assume next month
                    month = today.month + 1
                    year = today.year
                    if month > 12:
                        month = 1
                        year += 1
                    return datetime(year, month, day).date()
                else:
                    # Assume current month
                    return datetime(today.year, today.month, day).date()
            else:
                # Try standard yyyy-mm-dd format as a fallback
                return datetime.strptime(s_expiry, '%Y-%m-%d').date()

        except ValueError as e:
            logger.error(f"Invalid date format for '{expiry_input}': {e}")
            return None

    def _get_default_expiry(self) -> datetime.date:
        """
        Calculate the default expiration date (next upcoming Friday).
        If today is Friday, it will be next week's Friday.
        """
        today = datetime.now().date()
        days_until_friday = (4 - today.weekday() + 7) % 7

        if days_until_friday == 0:
            # If today is Friday, we want next Friday
            return today + timedelta(days=7)
        else:
            return today + timedelta(days=days_until_friday)

    def get_option_quote(self, symbol: Optional[str] = None, expiry: Optional[Union[str, int]] = None, strike: Optional[float] = None) -> Dict[str, Any]:
        """
        Get a formatted quote for a specific option strike.
        Handles complex defaulting logic for missing parameters.
        """
        if not self.schwab_client:
            return {"success": False, "error": "Schwab client not initialized."}

        try:
            # 1. Determine parameters using defaults if necessary
            last_request = state_manager.get_last_option_quote_request() or {}

            # Default symbol
            if not symbol:
                symbol = last_request.get('symbol')
                if not symbol: # Still no symbol, use the initial default
                    symbol = 'SPY'
                    logger.info("No symbol provided. Defaulting to SPY.")

            # Default expiry
            if not expiry:
                expiry = last_request.get('expiry')

            # Default strike
            if not strike:
                strike = last_request.get('strike')

            # 2. Resolve the final parameters
            if expiry:
                target_expiry = self._parse_expiry_date(expiry)
                if not target_expiry:
                    return {"success": False, "error": f"Invalid expiry date format: {expiry}"}
            else:
                target_expiry = self._get_default_expiry()

            if not strike:
                logger.info(f"No strike provided for {symbol}. Finding at-the-money strike.")
                chain_for_strikes = self.get_option_chains(symbol, fromDate=target_expiry.strftime('%Y-%m-%d'), toDate=target_expiry.strftime('%Y-%m-%d'))
                if not chain_for_strikes.get('success'):
                    return {"success": False, "error": f"Could not fetch option chain to determine strike for {symbol}"}

                underlying_price = chain_for_strikes.get('data', {}).get('underlyingPrice')
                if not underlying_price:
                    return {"success": False, "error": f"Underlying price not found in option chain for {symbol}"}

                all_strikes = list(chain_for_strikes.get('data', {}).get('callExpDateMap', {}).values())[0].keys()
                strike = min(all_strikes, key=lambda x: abs(float(x) - underlying_price))
                logger.info(f"Defaulting to closest strike price: {strike}")

            # 3. Fetch and format the data
            chain_response = self.get_option_chains(symbol, contractType='ALL', strike=strike, fromDate=target_expiry.strftime('%Y-%m-%d'), toDate=target_expiry.strftime('%Y-%m-%d'))
            if not chain_response.get('success'):
                return chain_response

            chain_data = chain_response.get('data', {})
            dte = (target_expiry - datetime.now().date()).days

            call_data = next((c[0] for _, s in chain_data.get('callExpDateMap', {}).items() for k, c in s.items() if float(k) == float(strike)), {})
            put_data = next((p[0] for _, s in chain_data.get('putExpDateMap', {}).items() for k, p in s.items() if float(k) == float(strike)), {})

            formatted_string = (
                f"{symbol} {dte} {strike} "
                f"CALL {call_data.get('last', 'N/A')} {call_data.get('bid', 'N/A')} {call_data.get('ask', 'N/A')} {call_data.get('totalVolume', 'N/A')} "
                f"PUT {put_data.get('last', 'N/A')} {put_data.get('bid', 'N/A')} {put_data.get('ask', 'N/A')} {put_data.get('totalVolume', 'N/A')}"
            )

            # 4. Save the successful request state
            state_manager.save_option_quote_request({
                'symbol': symbol,
                'expiry': target_expiry.strftime('%Y%m%d'),
                'strike': strike
            })

            return {"success": True, "data": formatted_string}

        except Exception as e:
            logger.error(f"Error in get_option_quote: {e}")
            return {"success": False, "error": str(e)}

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
            
            # Call schwabdev option_chains method
            options_response = self.schwab_client.option_chains(symbol=symbol, **kwargs)
            
            # Process the response
            if hasattr(options_response, 'json'):
                options_data = options_response.json()
                logger.info(f"Successfully retrieved option chains for {symbol}")
                
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