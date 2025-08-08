"""
Configuration module for Schwab API credentials and settings.
"""
import os
import json
import datetime
from typing import Optional
from creds_manager import CredsManager

class Config:
    """Configuration class for Schwab API settings."""
    
    def __init__(self):
        # Initialize credentials manager
        self.creds_manager = CredsManager()
        
        # Schwab API credentials - priority order:
        # 1. Environment variables (highest priority)
        # 2. creds.yml file
        # 3. Default values
        self.app_key: Optional[str] = os.getenv('SCHWAB_APP_KEY')
        self.app_secret: Optional[str] = os.getenv('SCHWAB_APP_SECRET')
        self.callback_url: str = os.getenv('SCHWAB_CALLBACK_URL', 'https://127.0.0.1:8182')
        self.tokens_file: str = os.getenv('SCHWAB_TOKENS_FILE', 'tokens.json')
        
        # Load from creds.yml if environment variables not set
        if not self.app_key or not self.app_secret:
            creds_app_key, creds_app_secret, creds_callback_url, creds_token_path = self.creds_manager.get_credentials()
            if creds_app_key and creds_app_secret:
                if not self.app_key:
                    self.app_key = creds_app_key
                if not self.app_secret:
                    self.app_secret = creds_app_secret
                if not os.getenv('SCHWAB_CALLBACK_URL'):
                    self.callback_url = creds_callback_url
                if not os.getenv('SCHWAB_TOKENS_FILE'):
                    self.tokens_file = creds_token_path
        
        # Server settings
        self.server_host: str = os.getenv('SERVER_HOST', 'localhost')
        self.server_port: int = int(os.getenv('SERVER_PORT', '3456'))
        
        # Request timeout
        self.timeout: int = int(os.getenv('REQUEST_TIMEOUT', '10'))
        
    def update_credentials(self, app_key: str, app_secret: str, 
                          callback_url: str = None, tokens_file: str = None):
        """Update API credentials."""
        self.app_key = app_key
        self.app_secret = app_secret
        if callback_url:
            self.callback_url = callback_url
        if tokens_file:
            self.tokens_file = tokens_file
    
    def is_configured(self) -> bool:
        """Check if required credentials are configured."""
        return bool(self.app_key and self.app_secret)
    
    def has_valid_tokens(self) -> bool:
        """
        Check if tokens.json exists and contains valid (non-expired) tokens.
        
        Returns:
            bool: True if valid tokens exist, False otherwise
        """
        try:
            if not os.path.exists(self.tokens_file):
                return False
                
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
                
            # Check if required token data exists
            token_dict = data.get("token_dictionary", {})
            if not token_dict.get("refresh_token"):
                return False
                
            # Check if refresh token is still valid (7 days from issue)
            refresh_issued_str = data.get("refresh_token_issued")
            if not refresh_issued_str:
                return False
                
            refresh_issued = datetime.datetime.fromisoformat(refresh_issued_str).replace(tzinfo=datetime.timezone.utc)
            refresh_timeout = 7 * 24 * 60 * 60  # 7 days in seconds
            time_since_issued = (datetime.datetime.now(datetime.timezone.utc) - refresh_issued).total_seconds()
            
            # Return True if refresh token is still valid (with 1 hour buffer)
            return time_since_issued < (refresh_timeout - 3600)
            
        except Exception:
            return False
    
    def can_start_with_tokens(self) -> bool:
        """
        Check if server can start using existing tokens without requiring credentials.
        
        Note: schwabdev library ALWAYS requires app_key, app_secret, and callback_url
        even when using existing tokens for token refresh operations.
        
        Returns:
            bool: True if server can start with tokens AND has stored credentials, False otherwise
        """
        return self.has_valid_tokens() and self._has_stored_credentials()
    
    def _has_stored_credentials(self) -> bool:
        """
        Check if credentials are available from environment or creds.yml.
        
        Returns:
            bool: True if credentials are available
        """
        # Check if we have credentials from any source
        return bool(self.app_key and self.app_secret)
    
    def get_stored_credentials(self) -> tuple:
        """
        Get credentials from environment or creds.yml.
        
        Returns:
            tuple: (app_key, app_secret, callback_url) or (None, None, None)
        """
        if self.app_key and self.app_secret:
            return self.app_key, self.app_secret, self.callback_url
        return None, None, None

# Global config instance
config = Config()