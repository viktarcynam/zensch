"""
Enhanced tokens management that stores credentials securely with tokens.
This addresses the schwabdev requirement for app_key/app_secret even with valid tokens.
"""
import json
import os
import base64
from cryptography.fernet import Fernet
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class EnhancedTokensManager:
    """Enhanced tokens manager that securely stores credentials with tokens."""
    
    def __init__(self, tokens_file: str = "tokens.json"):
        self.tokens_file = tokens_file
        self._key_file = f"{tokens_file}.key"
    
    def _get_or_create_key(self) -> bytes:
        """Get or create encryption key for credentials."""
        if os.path.exists(self._key_file):
            with open(self._key_file, 'rb') as f:
                return f.read()
        else:
            key = Fernet.generate_key()
            with open(self._key_file, 'wb') as f:
                f.write(key)
            # Set restrictive permissions
            os.chmod(self._key_file, 0o600)
            return key
    
    def _encrypt_credentials(self, app_key: str, app_secret: str, callback_url: str) -> dict:
        """Encrypt credentials for secure storage."""
        key = self._get_or_create_key()
        fernet = Fernet(key)
        
        credentials = {
            "app_key": app_key,
            "app_secret": app_secret,
            "callback_url": callback_url
        }
        
        credentials_json = json.dumps(credentials)
        encrypted = fernet.encrypt(credentials_json.encode())
        
        return {
            "encrypted_credentials": base64.b64encode(encrypted).decode(),
            "version": "1.0"
        }
    
    def _decrypt_credentials(self, encrypted_data: dict) -> Optional[Tuple[str, str, str]]:
        """Decrypt stored credentials."""
        try:
            if not os.path.exists(self._key_file):
                return None
                
            key = self._get_or_create_key()
            fernet = Fernet(key)
            
            encrypted_bytes = base64.b64decode(encrypted_data["encrypted_credentials"])
            decrypted = fernet.decrypt(encrypted_bytes)
            credentials = json.loads(decrypted.decode())
            
            return (
                credentials["app_key"],
                credentials["app_secret"], 
                credentials["callback_url"]
            )
        except Exception as e:
            logger.error(f"Failed to decrypt credentials: {e}")
            return None
    
    def enhance_tokens_file(self, app_key: str, app_secret: str, callback_url: str):
        """
        Enhance existing tokens.json file with encrypted credentials.
        
        Args:
            app_key: Schwab API app key
            app_secret: Schwab API app secret  
            callback_url: OAuth callback URL
        """
        try:
            # Read existing tokens file
            tokens_data = {}
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r') as f:
                    tokens_data = json.load(f)
            
            # Add encrypted credentials
            encrypted_creds = self._encrypt_credentials(app_key, app_secret, callback_url)
            tokens_data["stored_credentials"] = encrypted_creds
            tokens_data["enhanced_version"] = "1.0"
            
            # Write enhanced tokens file
            with open(self.tokens_file, 'w') as f:
                json.dump(tokens_data, f, indent=4)
            
            # Set restrictive permissions
            os.chmod(self.tokens_file, 0o600)
            
            logger.info("Enhanced tokens file with encrypted credentials")
            
        except Exception as e:
            logger.error(f"Failed to enhance tokens file: {e}")
            raise
    
    def get_stored_credentials(self) -> Optional[Tuple[str, str, str]]:
        """
        Get stored credentials from enhanced tokens file.
        
        Returns:
            tuple: (app_key, app_secret, callback_url) or None
        """
        try:
            if not os.path.exists(self.tokens_file):
                return None
                
            with open(self.tokens_file, 'r') as f:
                data = json.load(f)
            
            stored_creds = data.get("stored_credentials")
            if not stored_creds:
                return None
                
            return self._decrypt_credentials(stored_creds)
            
        except Exception as e:
            logger.error(f"Failed to get stored credentials: {e}")
            return None
    
    def has_stored_credentials(self) -> bool:
        """Check if enhanced tokens file has stored credentials."""
        return self.get_stored_credentials() is not None
    
    def remove_stored_credentials(self):
        """Remove stored credentials from tokens file."""
        try:
            if os.path.exists(self.tokens_file):
                with open(self.tokens_file, 'r') as f:
                    data = json.load(f)
                
                # Remove credentials
                data.pop("stored_credentials", None)
                data.pop("enhanced_version", None)
                
                with open(self.tokens_file, 'w') as f:
                    json.dump(data, f, indent=4)
            
            # Remove key file
            if os.path.exists(self._key_file):
                os.remove(self._key_file)
                
            logger.info("Removed stored credentials from tokens file")
            
        except Exception as e:
            logger.error(f"Failed to remove stored credentials: {e}")