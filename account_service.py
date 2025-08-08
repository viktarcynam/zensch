"""
Account service module for retrieving Schwab account information.
"""
import logging
from typing import Dict, List, Any, Optional
import json
from schwab_auth import SchwabAuthenticator

logger = logging.getLogger(__name__)

class AccountService:
    """Service for retrieving account information from Schwab API."""
    
    def __init__(self, authenticator: SchwabAuthenticator):
        """
        Initialize the account service.
        
        Args:
            authenticator: SchwabAuthenticator instance
        """
        self.authenticator = authenticator
    
    def get_linked_accounts(self) -> Dict[str, Any]:
        """
        Get all linked accounts for the authenticated user.
        
        Returns:
            Dict containing account information or error details
        """
        try:
            client = self.authenticator.get_client()
            response = client.account_linked()
            
            if response.status_code == 200:
                accounts_data = response.json()
                logger.info(f"Retrieved {len(accounts_data)} linked accounts")
                return {
                    'success': True,
                    'data': accounts_data,
                    'message': f'Successfully retrieved {len(accounts_data)} linked accounts'
                }
            else:
                error_msg = f"Failed to retrieve linked accounts. Status: {response.status_code}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            error_msg = f"Error retrieving linked accounts: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_account_details(self, account_hash: str, include_positions: bool = False) -> Dict[str, Any]:
        """
        Get detailed information for a specific account.
        
        Args:
            account_hash: The account hash from linked accounts
            include_positions: Whether to include position information
            
        Returns:
            Dict containing account details or error information
        """
        try:
            client = self.authenticator.get_client()
            
            # Set fields parameter to include positions if requested
            fields = "positions" if include_positions else None
            
            response = client.account_details(account_hash, fields=fields)
            
            if response.status_code == 200:
                account_data = response.json()
                logger.info(f"Retrieved account details for account hash: {account_hash}")
                return {
                    'success': True,
                    'data': account_data,
                    'message': f'Successfully retrieved account details for {account_hash}'
                }
            else:
                error_msg = f"Failed to retrieve account details. Status: {response.status_code}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            error_msg = f"Error retrieving account details: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_all_account_details(self, include_positions: bool = False) -> Dict[str, Any]:
        """
        Get detailed information for all linked accounts.
        
        Args:
            include_positions: Whether to include position information
            
        Returns:
            Dict containing all account details or error information
        """
        try:
            client = self.authenticator.get_client()
            
            # Set fields parameter to include positions if requested
            fields = "positions" if include_positions else None
            
            response = client.account_details_all(fields=fields)
            
            if response.status_code == 200:
                accounts_data = response.json()
                logger.info(f"Retrieved details for all accounts")
                return {
                    'success': True,
                    'data': accounts_data,
                    'message': 'Successfully retrieved details for all accounts'
                }
            else:
                error_msg = f"Failed to retrieve all account details. Status: {response.status_code}"
                logger.error(error_msg)
                return {
                    'success': False,
                    'error': error_msg,
                    'status_code': response.status_code
                }
                
        except Exception as e:
            error_msg = f"Error retrieving all account details: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }
    
    def get_account_summary(self, account_hash: str = None) -> Dict[str, Any]:
        """
        Get a summary of account information (balances, etc.) without positions.
        
        Args:
            account_hash: Specific account hash, or None for all accounts
            
        Returns:
            Dict containing account summary or error information
        """
        try:
            if account_hash:
                return self.get_account_details(account_hash, include_positions=False)
            else:
                return self.get_all_account_details(include_positions=False)
                
        except Exception as e:
            error_msg = f"Error retrieving account summary: {str(e)}"
            logger.error(error_msg)
            return {
                'success': False,
                'error': error_msg
            }