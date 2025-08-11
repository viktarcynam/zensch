# JULES: VERSION CHECK 2025-08-10 19:02
"""
Positions service module for retrieving Schwab account positions.
"""
import logging
from typing import Dict, List, Any, Optional
import json
from schwab_auth import SchwabAuthenticator

logger = logging.getLogger(__name__)

class PositionsService:
    """Service for retrieving position information from Schwab API."""
    
    def __init__(self, authenticator: SchwabAuthenticator):
        """
        Initialize the positions service.
        
        Args:
            authenticator: SchwabAuthenticator instance
        """
        self.authenticator = authenticator
    
    def get_positions(self, account_hash: str = None) -> Dict[str, Any]:
        """
        Get positions for a specific account or all accounts.
        
        Args:
            account_hash: Specific account hash, or None for all accounts
            
        Returns:
            Dict containing positions data or error information
        """
        try:
            client = self.authenticator.get_client()
            
            if account_hash:
                # Get positions for specific account
                response = client.account_details(account_hash, fields="positions")
                account_type = "specific account"
            else:
                # Get positions for all accounts
                response = client.account_details_all(fields="positions")
                account_type = "all accounts"
            
            if response.status_code == 200:
                data = response.json()
                positions_data = self._extract_positions(data, account_hash)
                
                logger.info(f"Retrieved positions for {account_type}")
                return {
                    'success': True,
                    'data': positions_data,
                    'message': f'Successfully retrieved positions for {account_type}'
                }
            else:
                error_msg = f"Failed to retrieve positions. Status: {response.status_code}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            error_msg = f"Error retrieving positions: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def _extract_positions(self, account_data: Any, account_hash: str = None) -> Dict[str, Any]:
        """
        Extract and format position information from account data.
        
        Args:
            account_data: Raw account data from API
            account_hash: Specific account hash if filtering for one account
            
        Returns:
            Dict containing formatted positions data
        """
        try:
            positions_summary = {
                'accounts': [],
                'total_positions': 0,
                'summary': {
                    'total_market_value': 0.0,
                    'total_day_change': 0.0,
                    'total_day_change_percent': 0.0
                }
            }
            
            # Handle both single account and multiple accounts response
            accounts_list = account_data if isinstance(account_data, list) else [account_data]
            
            for account in accounts_list:
                if 'securitiesAccount' in account:
                    account_info = account['securitiesAccount']
                    account_hash_key = account_info.get('accountNumber', 'Unknown')
                    
                    account_positions = {
                        'accountHash': account_hash_key,
                        'accountType': account_info.get('type', 'Unknown'),
                        'positions': [],
                        'account_summary': {
                            'total_market_value': 0.0,
                            'total_day_change': 0.0,
                            'position_count': 0
                        }
                    }
                    
                    # Extract positions if they exist
                    if 'positions' in account_info:
                        for position in account_info['positions']:
                            position_data = self._format_position(position)
                            account_positions['positions'].append(position_data)
                            
                            # Update account summary
                            account_positions['account_summary']['total_market_value'] += position_data.get('marketValue', 0.0)
                            account_positions['account_summary']['total_day_change'] += position_data.get('dayChange', 0.0)
                            account_positions['account_summary']['position_count'] += 1
                    
                    positions_summary['accounts'].append(account_positions)
                    positions_summary['total_positions'] += account_positions['account_summary']['position_count']
                    positions_summary['summary']['total_market_value'] += account_positions['account_summary']['total_market_value']
                    positions_summary['summary']['total_day_change'] += account_positions['account_summary']['total_day_change']
            
            # Calculate total day change percentage
            if positions_summary['summary']['total_market_value'] > 0:
                total_cost_basis = positions_summary['summary']['total_market_value'] - positions_summary['summary']['total_day_change']
                if total_cost_basis > 0:
                    positions_summary['summary']['total_day_change_percent'] = (
                        positions_summary['summary']['total_day_change'] / total_cost_basis * 100
                    )
            
            return positions_summary
            
        except Exception as e:
            logger.error(f"Error extracting positions: {str(e)}")
            return {
                'accounts': [],
                'total_positions': 0,
                'error': f"Error processing positions data: {str(e)}"
            }
    
    def _format_position(self, position: Dict[str, Any]) -> Dict[str, Any]:
        """
        Format a single position for consistent output.
        
        Args:
            position: Raw position data from API
            
        Returns:
            Dict containing formatted position data
        """
        try:
            instrument = position.get('instrument', {})
            
            formatted_position = {
                'symbol': instrument.get('symbol', 'Unknown'),
                'description': instrument.get('description', ''),
                'assetType': instrument.get('assetType', 'Unknown'),
                'quantity': position.get('longQuantity', 0.0) + position.get('shortQuantity', 0.0),
                'longQuantity': position.get('longQuantity', 0.0),
                'shortQuantity': position.get('shortQuantity', 0.0),
                'averagePrice': position.get('averagePrice', 0.0),
                'marketValue': position.get('marketValue', 0.0),
                'dayChange': position.get('currentDayProfitLoss', 0.0),
                'dayChangePercent': position.get('currentDayProfitLossPercentage', 0.0),
                'totalProfitLoss': position.get('longQuantity', 0.0) * position.get('averagePrice', 0.0) - position.get('marketValue', 0.0),
                'cusip': instrument.get('cusip', ''),
                'instrumentType': instrument.get('type', 'Unknown'),
                'underlyingSymbol': instrument.get('underlyingSymbol', '')
            }
            
            # Calculate total profit/loss percentage
            cost_basis = formatted_position['quantity'] * formatted_position['averagePrice']
            if cost_basis > 0:
                formatted_position['totalProfitLossPercent'] = (
                    (formatted_position['marketValue'] - cost_basis) / cost_basis * 100
                )
            else:
                formatted_position['totalProfitLossPercent'] = 0.0
            
            return formatted_position
            
        except Exception as e:
            logger.error(f"Error formatting position: {str(e)}")
            return {
                'symbol': 'Error',
                'error': f"Error formatting position: {str(e)}"
            }
    
    def get_positions_by_symbol(self, symbol: str, account_hash: str = None) -> Dict[str, Any]:
        """
        Get positions for a specific symbol across accounts.
        
        Args:
            symbol: Stock symbol to filter by
            account_hash: Specific account hash, or None for all accounts
            
        Returns:
            Dict containing filtered positions data
        """
        try:
            positions_result = self.get_positions(account_hash)
            
            if not positions_result['success']:
                return positions_result
            
            filtered_positions = {
                'symbol': symbol.upper(),
                'accounts': [],
                'total_quantity': 0.0,
                'total_market_value': 0.0
            }
            
            for account in positions_result['data']['accounts']:
                account_positions = []
                for position in account['positions']:
                    if position['symbol'].upper() == symbol.upper() or position['underlyingSymbol'].upper() == symbol.upper():
                        account_positions.append(position)
                        filtered_positions['total_quantity'] += position['quantity']
                        filtered_positions['total_market_value'] += position['marketValue']
                
                if account_positions:
                    filtered_positions['accounts'].append({
                        'accountHash': account['accountHash'],
                        'accountType': account['accountType'],
                        'positions': account_positions
                    })
            
            return {
                'success': True,
                'data': filtered_positions,
                'message': f'Successfully retrieved positions for symbol {symbol}'
            }
            
        except Exception as e:
            error_msg = f"Error retrieving positions for symbol {symbol}: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }