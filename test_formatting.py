import unittest
from unittest.mock import MagicMock, patch
from quotes_service import QuotesService
from options_service import OptionsService
from datetime import datetime, date

class TestFormatting(unittest.TestCase):

    def setUp(self):
        self.mock_schwab_client = MagicMock()
        self.quotes_service = QuotesService(self.mock_schwab_client)
        self.options_service = OptionsService(self.mock_schwab_client)

    def test_equity_quote_formatting(self):
        # Mock the API response for quotes
        mock_response = {
            "AAPL": {
                "quote": {
                    "symbol": "AAPL",
                    "lastPrice": 150.0,
                    "bidPrice": 149.9,
                    "askPrice": 150.1,
                    "totalVolume": 1000000
                }
            },
            "MSFT": {
                "quote": {
                    "symbol": "MSFT",
                    "lastPrice": 300.0,
                    "bidPrice": 299.9,
                    "askPrice": 300.1,
                    "totalVolume": 2000000
                }
            }
        }
        self.mock_schwab_client.quotes.return_value.json.return_value = mock_response

        # Call the get_quotes method
        result = self.quotes_service.get_quotes(symbols=["AAPL", "MSFT"])

        # Assert the result
        self.assertTrue(result['success'])
        self.assertEqual(len(result['data']), 2)
        self.assertEqual(result['data'][0], "AAPL 150.0 149.9 150.1 1000000")
        self.assertEqual(result['data'][1], "MSFT 300.0 299.9 300.1 2000000")

    def test_option_quote_formatting(self):
        # Mock the API response for option chains
        mock_chain = {
            "underlyingPrice": 150.0,
            "callExpDateMap": {
                "2024-12-20:0": {
                    "155.0": [{
                        "last": 5.0,
                        "bid": 4.9,
                        "ask": 5.1,
                        "totalVolume": 1000
                    }]
                }
            },
            "putExpDateMap": {
                "2024-12-20:0": {
                    "155.0": [{
                        "last": 2.0,
                        "bid": 1.9,
                        "ask": 2.1,
                        "totalVolume": 2000
                    }]
                }
            }
        }
        self.mock_schwab_client.option_chains.return_value.json.return_value = mock_chain

        # Mock the date to be consistent
        with patch('options_service.datetime') as mock_date:
            mock_date.now.return_value = datetime(2024, 8, 9)
            mock_date.strptime = datetime.strptime

            # Call the get_option_quote method
            result = self.options_service.get_option_quote(symbol="AAPL", expiry="20241220", strike=155)

            # Assert the result
            self.assertTrue(result['success'])
            dte = (date(2024, 12, 20) - date(2024, 8, 9)).days
            expected_string = f"AAPL {dte} 155 CALL 5.0 4.9 5.1 1000 PUT 2.0 1.9 2.1 2000"
            self.assertEqual(result['data'], expected_string)

if __name__ == '__main__':
    unittest.main()
