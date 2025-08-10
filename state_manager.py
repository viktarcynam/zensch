import json
import logging
from typing import Dict, Any, Optional

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger('state_manager')

class StateManager:
    """Handles loading and saving of the application's persistent state."""

    def __init__(self, state_file: str = 'last_quote_state.json'):
        self.state_file = state_file
        self.state = self._load_state()

    def _load_state(self) -> Dict[str, Any]:
        """Loads the state from the JSON file."""
        try:
            with open(self.state_file, 'r') as f:
                state = json.load(f)
                logger.info(f"Loaded state from {self.state_file}")
                return state
        except FileNotFoundError:
            logger.info(f"State file not found. Initializing with empty state.")
            return {}
        except json.JSONDecodeError:
            logger.warning(f"Could not decode JSON from {self.state_file}. Starting with empty state.")
            return {}

    def _save_state(self):
        """Saves the current state to the JSON file."""
        try:
            with open(self.state_file, 'w') as f:
                json.dump(self.state, f, indent=4)
                logger.info(f"Saved state to {self.state_file}")
        except IOError as e:
            logger.error(f"Could not write to state file {self.state_file}: {e}")

    def get_last_stock_quote_request(self) -> Optional[Dict[str, Any]]:
        """Returns the parameters of the last successful stock quote request."""
        return self.state.get('last_stock_quote')

    def save_stock_quote_request(self, params: Dict[str, Any]):
        """Saves the parameters of a successful stock quote request."""
        self.state['last_stock_quote'] = params
        self._save_state()

    def get_last_option_quote_request(self) -> Optional[Dict[str, Any]]:
        """Returns the parameters of the last successful option quote request."""
        return self.state.get('last_option_quote')

    def save_option_quote_request(self, params: Dict[str, Any]):
        """Saves the parameters of a successful option quote request."""
        self.state['last_option_quote'] = params
        self._save_state()

# Create a singleton instance for the application to use
state_manager = StateManager()
