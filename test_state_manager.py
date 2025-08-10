import unittest
import json
from unittest.mock import patch, mock_open
from state_manager import StateManager

class TestStateManager(unittest.TestCase):

    def test_load_state_success(self):
        read_data = '{"last_stock_quote": {"symbols": ["AAPL"]}}'
        with patch("builtins.open", mock_open(read_data=read_data)) as mock_file:
            manager = StateManager()
            self.assertEqual(manager.get_last_stock_quote_request(), {"symbols": ["AAPL"]})

    def test_load_state_file_not_found(self):
        with patch("builtins.open", side_effect=FileNotFoundError) as mock_file:
            manager = StateManager()
            self.assertEqual(manager.state, {})

    def test_load_state_json_decode_error(self):
        with patch("builtins.open", mock_open(read_data='{invalid json}')) as mock_file:
            manager = StateManager()
            self.assertEqual(manager.state, {})

    def test_save_stock_quote(self):
        with patch("builtins.open", mock_open()) as mock_file:
            # We need to initialize the manager inside the mock context
            manager = StateManager(state_file='test.json')
            manager.state = {} # Start with a clean slate

            params = {"symbols": ["MSFT"]}
            manager.save_stock_quote_request(params)

            mock_file.assert_called_with('test.json', 'w')
            handle = mock_file()

            # Get all the writes, join them, and then load
            written_data = "".join(call.args[0] for call in handle.write.call_args_list)
            saved_data = json.loads(written_data)
            self.assertEqual(saved_data['last_stock_quote'], params)

    def test_save_option_quote(self):
        with patch("builtins.open", mock_open()) as mock_file:
            manager = StateManager(state_file='test.json')
            manager.state = {} # Start with a clean slate

            params = {'symbol': 'GOOG', 'expiry': '20241220', 'strike': 150}
            manager.save_option_quote_request(params)

            mock_file.assert_called_with('test.json', 'w')
            handle = mock_file()

            written_data = "".join(call.args[0] for call in handle.write.call_args_list)
            saved_data = json.loads(written_data)
            self.assertEqual(saved_data['last_option_quote'], params)

if __name__ == '__main__':
    unittest.main()
