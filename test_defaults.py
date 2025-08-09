import unittest
from unittest.mock import patch, MagicMock
from quotes_service import QuotesService
from options_service import OptionsService

class TestDefaulting(unittest.TestCase):

    def setUp(self):
        self.mock_schwab_client = MagicMock()
        # Mock the quotes response for SPY
        self.mock_schwab_client.quotes.return_value.json.return_value = {
            "SPY": {"quote": {"symbol": "SPY", "lastPrice": 450.0}}
        }
        self.quotes_service = QuotesService(self.mock_schwab_client)
        self.options_service = OptionsService(self.mock_schwab_client)

    @patch('quotes_service.state_manager')
    def test_get_quotes_no_state_default(self, mock_state_manager):
        # No state exists
        mock_state_manager.get_last_stock_quote_request.return_value = None

        # Call get_quotes with no symbols
        result = self.quotes_service.get_quotes()

        # Assert it defaulted to SPY
        self.assertTrue(result['success'])
        self.assertIn("SPY 450.0", result['data'][0])
        # Assert that the state was saved
        mock_state_manager.save_stock_quote_request.assert_called_with({'symbols': ['SPY']})

    @patch('quotes_service.state_manager')
    def test_get_quotes_with_state_default(self, mock_state_manager):
        # State exists
        mock_state_manager.get_last_stock_quote_request.return_value = {"symbols": ["TSLA"]}

        # Mock the response for TSLA
        self.mock_schwab_client.quotes.return_value.json.return_value = {
            "TSLA": {"quote": {"symbol": "TSLA", "lastPrice": 250.0}}
        }

        # Call get_quotes with no symbols
        result = self.quotes_service.get_quotes()

        # Assert it used the state
        self.assertTrue(result['success'])
        self.assertIn("TSLA 250.0", result['data'][0])
        # Assert that the state was re-saved
        mock_state_manager.save_stock_quote_request.assert_called_with({'symbols': ['TSLA']})

    @patch('options_service.state_manager')
    @patch('options_service.quotes_service')
    def test_get_option_quote_full_default(self, mock_quotes_service, mock_state_manager):
        # No state exists
        mock_state_manager.get_last_option_quote_request.return_value = None

        # Mock the chain response for SPY to find the strike
        self.mock_schwab_client.option_chains.return_value.json.return_value = {
            "underlyingPrice": 450.0,
            "callExpDateMap": {"2024-12-20:0": {"450.0": [{"last": 10.0}]}},
            "putExpDateMap": {"2024-12-20:0": {"450.0": [{"last": 12.0}]}}
        }

        with patch('options_service.datetime') as mock_date:
            mock_date.now.return_value.date.return_value = unittest.mock.MagicMock(weekday=lambda: 0) # Monday
            mock_date.now.return_value = unittest.mock.MagicMock(date=lambda: unittest.mock.MagicMock(weekday=lambda: 0))

            # Call with no parameters
            result = self.options_service.get_option_quote()

            # Assert it defaulted to SPY and at-the-money strike
            self.assertTrue(result['success'])
            self.assertIn("SPY", result['data'])
            self.assertIn("450.0", result['data'])

            # Assert state was saved
            mock_state_manager.save_option_quote_request.assert_called()

if __name__ == '__main__':
    unittest.main()
