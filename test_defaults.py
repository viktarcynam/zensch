import unittest
from unittest.mock import patch, MagicMock
from quotes_service import QuotesService
from options_service import OptionsService
from datetime import date, datetime

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
    def test_get_option_quote_full_default(self, mock_state_manager):
        # No state exists
        mock_state_manager.get_last_option_quote_request.return_value = None

        # Mock the chain response for SPY to find the strike
        self.mock_schwab_client.option_chains.return_value.json.return_value = {
            "underlyingPrice": 450.0,
            "callExpDateMap": {"2024-12-20:0": {"450.0": [{"last": 10.0}]}},
            "putExpDateMap": {"2024-12-20:0": {"450.0": [{"last": 12.0}]}}
        }

        with patch('options_service.datetime') as mock_date:
            mock_date.now.return_value = datetime(2024, 8, 9) # A Friday
            mock_date.strptime = datetime.strptime

            # Call with no parameters
            result = self.options_service.get_option_quote()

            # Assert it defaulted to SPY and at-the-money strike
            self.assertTrue(result['success'])
            self.assertIn("SPY", result['data'])
            self.assertIn("450.0", result['data'])

            # Assert state was saved
            mock_state_manager.save_option_quote_request.assert_called()

    @patch('options_service.state_manager')
    def test_get_option_quote_new_symbol_defaults(self, mock_state_manager):
        # State exists for a different symbol
        mock_state_manager.get_last_option_quote_request.return_value = {
            "symbol": "AAPL", "expiry": "20241220", "strike": 190
        }

        # Mock the chain response for the new symbol (MSFT)
        self.mock_schwab_client.option_chains.return_value.json.return_value = {
            "underlyingPrice": 400.0,
            "callExpDateMap": {"2025-01-17:0": {"400.0": [{"last": 20.0}]}},
            "putExpDateMap": {"2025-01-17:0": {"400.0": [{"last": 22.0}]}}
        }

        with patch('options_service.datetime') as mock_date:
            mock_date.now.return_value = datetime(2024, 8, 10) # Saturday
            mock_date.strptime = datetime.strptime

            # Call with a new symbol, no strike or expiry
            result = self.options_service.get_option_quote(symbol="MSFT")

            self.assertTrue(result['success'])
            self.assertIn("MSFT", result['data'])
            self.assertIn("400.0", result['data'])

            saved_args = mock_state_manager.save_option_quote_request.call_args[0][0]
            self.assertEqual(saved_args['symbol'], 'MSFT')
            self.assertEqual(saved_args['strike'], '400.0')

    @patch('options_service.state_manager')
    def test_get_option_quote_same_symbol_uses_state(self, mock_state_manager):
        # State exists for AAPL
        mock_state_manager.get_last_option_quote_request.return_value = {
            "symbol": "AAPL", "expiry": "20241220", "strike": 190
        }

        self.mock_schwab_client.option_chains.return_value.json.return_value = {
            "underlyingPrice": 185.0,
            "callExpDateMap": {"2024-12-20:0": {"190": [{"last": 5.0}]}},
            "putExpDateMap": {"2024-12-20:0": {"190": [{"last": 6.0}]}}
        }

        with patch('options_service.datetime') as mock_date:
            mock_date.now.return_value = datetime(2024, 8, 10)
            mock_date.strptime = datetime.strptime

            result = self.options_service.get_option_quote(symbol="AAPL")

            self.assertTrue(result['success'])
            self.assertIn("AAPL", result['data'])
            self.assertIn("190", result['data'])

            saved_args = mock_state_manager.save_option_quote_request.call_args[0][0]
            self.assertEqual(saved_args['symbol'], 'AAPL')
            self.assertEqual(saved_args['expiry'], '20241220')
            self.assertEqual(saved_args['strike'], 190)

if __name__ == '__main__':
    unittest.main()
