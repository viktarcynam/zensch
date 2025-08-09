#!/usr/bin/env python3
"""
Example script demonstrating the use of the get_option_quote feature.
"""
import json
import logging
from client import SchwabClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to demonstrate option quote functionality."""
    logger.info("Schwab API Option Quote Example")
    logger.info("=" * 50)

    with SchwabClient() as client:
        if not client.ping().get('success'):
            logger.error("Server is not running. Please start the server first.")
            return

        logger.info("Server is running. Testing option quotes...")

        # NOTE: These examples require valid credentials and a running server.
        # They will likely fail without authentication.

        # Example 1: Specific symbol, expiry, and strike
        logger.info("\nExample 1: Get option quote for a specific symbol, expiry, and strike")
        response = client.send_request({
            "action": "get_option_quote",
            "symbol": "AAPL",
            "expiry": "20241220",  # yyyymmdd format
            "strike": 190
        })
        print_response(response)

        # Example 2: Default strike, specific expiry
        logger.info("\nExample 2: Get option quote with default (at-the-money) strike")
        response = client.send_request({
            "action": "get_option_quote",
            "symbol": "MSFT",
            "expiry": "1220"  # mmdd format
        })
        print_response(response)

        # Example 3: Default expiry, specific strike
        logger.info("\nExample 3: Get option quote with default expiry (next Friday)")
        response = client.send_request({
            "action": "get_option_quote",
            "symbol": "NVDA",
            "strike": 800
        })
        print_response(response)

        # Example 4: Default expiry and strike
        logger.info("\nExample 4: Get option quote with default expiry and strike")
        response = client.send_request({
            "action": "get_option_quote",
            "symbol": "TSLA"
        })
        print_response(response)

        # Example 5: 'dd' date format
        logger.info("\nExample 5: Using 'dd' for expiry date")
        response = client.send_request({
            "action": "get_option_quote",
            "symbol": "GOOG",
            "expiry": "20", # Assumes the 20th of the current or next month
            "strike": 140
        })
        print_response(response)

        # Example 6: Fully defaulted (no arguments)
        logger.info("\nExample 6: Get option quote with no arguments")
        logger.info("This will use the last successful request's parameters (from Example 5).")
        response = client.send_request({"action": "get_option_quote"})
        print_response(response)


def print_response(response):
    """Print a formatted response."""
    if response.get('success'):
        logger.info("Request successful")
        data = response.get('data', "")
        logger.info(f"Formatted Quote: {data}")
    else:
        logger.error(f"Request failed: {response.get('error')}")

if __name__ == "__main__":
    main()
