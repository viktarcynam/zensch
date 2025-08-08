"""
Schwab API authentication module.
Handles authentication and session management for the Schwab API.
"""
import logging
from typing import Optional
import schwabdev
from config import config

logger = logging.getLogger(__name__)

class SchwabAuthenticator:
    """Handles Schwab API authentication and client management."""
    
    def __init__(self, app_key: str = None, app_secret: str = None, 
                 callback_url: str = None, tokens_file: str = None, 
                 allow_tokens_only: bool = False):
        """
        Initialize the authenticator.
        
        Args:
            app_key: Schwab API app key
            app_secret: Schwab API app secret
            callback_url: OAuth callback URL
            tokens_file: Path to tokens file
            allow_tokens_only: Allow initialization with tokens.json only (no credentials required)
        """
        self.app_key = app_key or config.app_key
        self.app_secret = app_secret or config.app_secret
        self.callback_url = callback_url or config.callback_url
        self.tokens_file = tokens_file or config.tokens_file
        self.client: Optional[schwabdev.Client] = None
        self.allow_tokens_only = allow_tokens_only
        
        # If tokens-only mode and valid tokens exist, try to get credentials from config
        if allow_tokens_only and config.has_valid_tokens() and (not self.app_key or not self.app_secret):
            try:
                # Try to get credentials from config (environment or creds.yml)
                stored_key, stored_secret, stored_callback = config.get_stored_credentials()
                
                if stored_key and stored_secret:
                    if not self.app_key:
                        self.app_key = stored_key
                    if not self.app_secret:
                        self.app_secret = stored_secret
                    if not self.callback_url:
                        self.callback_url = stored_callback
                    logger.info("Using tokens-only mode with credentials from config")
                else:
                    logger.warning("Tokens-only mode requested but no credentials found")
                    logger.warning("schwabdev requires app_key and app_secret even with valid tokens")
                    
            except Exception as e:
                logger.warning(f"Could not set up tokens-only mode: {e}")
        
        if not self.app_key or not self.app_secret:
            if allow_tokens_only:
                raise ValueError("App key and app secret are required, or valid tokens.json must exist for tokens-only mode")
            else:
                raise ValueError("App key and app secret are required for authentication")
    
    def authenticate(self) -> schwabdev.Client:
        """
        Authenticate with Schwab API and return client.
        
        Returns:
            schwabdev.Client: Authenticated Schwab client
            
        Raises:
            Exception: If authentication fails
        """
        try:
            logger.info("Authenticating with Schwab API...")
            
            # Create the client - this will handle token management automatically
            self.client = schwabdev.Client(
                app_key=self.app_key,
                app_secret=self.app_secret,
                callback_url=self.callback_url,
                tokens_file=self.tokens_file,
                timeout=config.timeout,
                capture_callback=True,  # Use webserver to capture callback
                use_session=True  # Use session for better performance
            )
            
            logger.info("Successfully authenticated with Schwab API")
            return self.client
            
        except Exception as e:
            logger.error(f"Authentication failed: {str(e)}")
            raise Exception(f"Failed to authenticate with Schwab API: {str(e)}")
    
    def get_client(self) -> schwabdev.Client:
        """
        Get the authenticated client, authenticating if necessary.
        
        Returns:
            schwabdev.Client: Authenticated Schwab client
        """
        if self.client is None:
            self.authenticate()
        return self.client
    
    def is_authenticated(self) -> bool:
        """
        Check if client is authenticated.
        
        Returns:
            bool: True if authenticated, False otherwise
        """
        return self.client is not None
    
    def test_connection(self) -> bool:
        """
        Test the connection by making a simple API call.
        
        Returns:
            bool: True if connection is working, False otherwise
        """
        try:
            client = self.get_client()
            # Test with a simple call to get linked accounts
            response = client.account_linked()
            return response.status_code == 200
        except Exception as e:
            logger.error(f"Connection test failed: {str(e)}")
            return False