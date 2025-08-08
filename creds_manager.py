"""
Credentials manager for reading from creds.yml file.
Keeps schwabdev tokens.json format unchanged.
"""
import os
import yaml
from typing import Optional, Tuple
import logging

logger = logging.getLogger(__name__)

class CredsManager:
    """Manages credentials from creds.yml file."""
    
    def __init__(self, creds_file: str = "creds.yml"):
        self.creds_file = creds_file
    
    def load_credentials(self) -> Optional[dict]:
        """
        Load credentials from creds.yml file.
        
        Returns:
            dict: Credentials dictionary or None if file doesn't exist/invalid
        """
        try:
            if not os.path.exists(self.creds_file):
                return None
                
            with open(self.creds_file, 'r') as f:
                creds = yaml.safe_load(f)
                
            # Validate required keys
            required_keys = ['app_key', 'app_secret', 'callback_url', 'token_path']
            if not all(key in creds for key in required_keys):
                logger.error(f"Missing required keys in {self.creds_file}. Required: {required_keys}")
                return None
                
            # Validate credential formats
            if len(creds['app_key']) != 32:
                logger.error("app_key must be 32 characters long")
                return None
                
            if len(creds['app_secret']) != 16:
                logger.error("app_secret must be 16 characters long")
                return None
                
            if not creds['callback_url'].startswith('https'):
                logger.error("callback_url must start with https")
                return None
                
            return creds
            
        except yaml.YAMLError as e:
            logger.error(f"Error parsing {self.creds_file}: {e}")
            return None
        except Exception as e:
            logger.error(f"Error loading {self.creds_file}: {e}")
            return None
    
    def get_credentials(self) -> Tuple[Optional[str], Optional[str], Optional[str], Optional[str]]:
        """
        Get credentials from creds.yml.
        
        Returns:
            tuple: (app_key, app_secret, callback_url, token_path) or (None, None, None, None)
        """
        creds = self.load_credentials()
        if creds:
            return (
                creds['app_key'],
                creds['app_secret'], 
                creds['callback_url'],
                creds['token_path']
            )
        return None, None, None, None
    
    def has_valid_credentials(self) -> bool:
        """Check if creds.yml exists and has valid credentials."""
        creds = self.load_credentials()
        return creds is not None
    
    def create_sample_creds_file(self):
        """Create a sample creds.yml file with placeholder values."""
        sample_creds = {
            'app_key': 'your_32_character_app_key_here_123',  # 32 chars
            'app_secret': 'your_16_char_key1',  # 16 chars
            'callback_url': 'https://127.0.0.1:8182',
            'token_path': 'tokens.json'
        }
        
        try:
            with open(self.creds_file, 'w') as f:
                yaml.dump(sample_creds, f, default_flow_style=False, indent=2)
            
            # Set restrictive permissions
            os.chmod(self.creds_file, 0o600)
            
            logger.info(f"Created sample {self.creds_file} file")
            print(f"Created sample {self.creds_file} file. Please edit it with your actual credentials.")
            
        except Exception as e:
            logger.error(f"Failed to create sample {self.creds_file}: {e}")
            raise