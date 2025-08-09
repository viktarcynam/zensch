#!/usr/bin/env python3
"""
Example script demonstrating the use of the options feature.
"""
import json
import logging
from client import SchwabClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to demonstrate options functionality."""
    logger.info("Schwab API Options Example")
    logger.info("=" * 50)
    
    # Connect to the server
    with SchwabClient() as client:
        # Check if server is running
        ping_response = client.ping()
        if not ping_response.get('success'):
            logger.error("Server is not running. Please start the server first.")
            return
        
        logger.info("Server is running. Testing options functionality...")
        
        # Example 1: Get option chains for a symbol with default parameters
        logger.info("\nExample 1: Get option chains for a symbol with default parameters")
        response = client.get_option_chains("AAPL")
        print_response(response)
        
        # Example 2: Get option chains with specific parameters
        logger.info("\nExample 2: Get option chains with specific parameters")
        response = client.get_option_chains(
            symbol="MSFT",
            contractType="CALL",
            strikeCount=5,
            includeUnderlyingQuote=True
        )
        print_response(response)
        
        # Example 3: Get option chains with date range
        logger.info("\nExample 3: Get option chains with date range")
        from datetime import datetime, timedelta
        today = datetime.now()
        one_month_later = today + timedelta(days=30)
        
        response = client.get_option_chains(
            symbol="GOOG",
            fromDate=today.strftime("%Y-%m-%d"),
            toDate=one_month_later.strftime("%Y-%m-%d"),
            range="ITM"
        )
        print_response(response)
        
        # Example 4: Using JSON string
        logger.info("\nExample 4: Using JSON string")
        json_request = '''
        {
            "action": "get_option_chains",
            "symbol": "TSLA",
            "contractType": "PUT",
            "strategy": "SINGLE",
            "range": "OTM"
        }
        '''
        response = client.send_request(json_request)
        print_response(response)
        
        # Example 5: Using JSON file
        logger.info("\nExample 5: Using JSON file")
        response = client.send_from_file("example_requests/get_option_chains.json")
        print_response(response)
        
        # Example 6: Using JSON file with overrides
        logger.info("\nExample 6: Using JSON file with overrides")
        response = client.send_request(
            "example_requests/get_option_chains.json",
            '{"symbol": "SPY", "strikeCount": 3}'
        )
        print_response(response)

def print_response(response):
    """Print a formatted response."""
    if response.get('success'):
        logger.info("Request successful")
        # Print first part of data to avoid overwhelming output
        data = response.get('data', {})
        if isinstance(data, list) and len(data) > 0:
            logger.info(f"Received {len(data)} option chain(s)")
            # Print first option chain as sample
            logger.info(f"Sample option chain: {json.dumps(data[0], indent=2)[:500]}...")
        elif isinstance(data, dict):
            # Print first 500 chars of the data
            logger.info(f"Data: {json.dumps(data, indent=2)[:500]}...")
    else:
        logger.error(f"Request failed: {response.get('error')}")

if __name__ == "__main__":
    main()