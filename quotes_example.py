#!/usr/bin/env python3
"""
Example script demonstrating the use of the quotes feature.
"""
import json
import logging
from client import SchwabClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to demonstrate quotes functionality."""
    logger.info("Schwab API Quotes Example")
    logger.info("=" * 50)
    
    # Connect to the server
    with SchwabClient() as client:
        # Check if server is running
        ping_response = client.ping()
        if not ping_response.get('success'):
            logger.error("Server is not running. Please start the server first.")
            return
        
        logger.info("Server is running. Testing quotes functionality...")
        
        # Example 1: Get quotes for a single symbol
        logger.info("\nExample 1: Get quotes for a single symbol")
        response = client.get_quotes("AAPL")
        print_response(response)
        
        # Example 2: Get quotes for multiple symbols
        logger.info("\nExample 2: Get quotes for multiple symbols")
        response = client.get_quotes(["MSFT", "GOOG", "AMZN"])
        print_response(response)
        
        # Example 3: Get quotes with specific fields
        logger.info("\nExample 3: Get quotes with specific fields")
        response = client.get_quotes("TSLA", fields="fundamental")
        print_response(response)
        
        # Example 4: Using JSON string
        logger.info("\nExample 4: Using JSON string")
        json_request = '''
        {
            "action": "get_quotes",
            "symbols": ["NVDA", "AMD"],
            "fields": "quote"
        }
        '''
        response = client.send_request(json_request)
        print_response(response)
        
        # Example 5: Using JSON file
        logger.info("\nExample 5: Using JSON file")
        response = client.send_from_file("example_requests/get_quotes.json")
        print_response(response)

def print_response(response):
    """Print a formatted response."""
    if response.get('success'):
        logger.info("Request successful")
        data = response.get('data', [])
        if isinstance(data, list):
            logger.info(f"Received {len(data)} quote(s):")
            for item in data:
                logger.info(f"  - {item}")
        elif isinstance(data, str):
            logger.info(f"Data: {data}")
        else:
            logger.info(f"Data: {json.dumps(data, indent=2)}")
    else:
        logger.error(f"Request failed: {response.get('error')}")

if __name__ == "__main__":
    main()