#!/usr/bin/env python3
"""
Example script demonstrating the use of streaming data features.
"""
import json
import logging
import time
from client import SchwabClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to demonstrate streaming functionality."""
    logger.info("Schwab API Streaming Example")
    logger.info("=" * 50)
    
    # Connect to the server
    with SchwabClient() as client:
        # Check if server is running
        ping_response = client.ping()
        if not ping_response.get('success'):
            logger.error("Server is not running. Please start the server first.")
            return
        
        logger.info("Server is running. Testing streaming functionality...")
        
        # Example 1: Get a regular quote (no streaming)
        logger.info("\nExample 1: Get a regular quote (no streaming)")
        response = client.send_request(json.dumps({
            "action": "get_quotes",
            "symbols": "AAPL",
            "fields": "all",
            "use_streaming": False
        }))
        print_response(response)
        
        # Example 2: Get a quote and add to streaming
        logger.info("\nExample 2: Get a quote and add to streaming")
        response = client.send_request(json.dumps({
            "action": "get_quotes",
            "symbols": "MSFT",
            "fields": "all",
            "use_streaming": False  # Still adding to streaming but not using streaming data
        }))
        print_response(response)
        
        # Wait a moment for streaming to initialize
        logger.info("\nWaiting for streaming data to initialize...")
        time.sleep(5)
        
        # Example 3: Get a streaming quote
        logger.info("\nExample 3: Get a streaming quote")
        response = client.send_request(json.dumps({
            "action": "get_quotes",
            "symbols": "AAPL",
            "fields": "all",
            "use_streaming": True  # Now use streaming data if available
        }))
        print_response(response)
        
        # Example 4: Get a streaming quote for a different symbol
        logger.info("\nExample 4: Get a streaming quote for a different symbol")
        response = client.send_request(json.dumps({
            "action": "get_quotes",
            "symbols": "MSFT",
            "fields": "all",
            "use_streaming": True
        }))
        print_response(response)
        
        # Example 5: Get option chain data
        logger.info("\nExample 5: Get option chain data")
        response = client.send_request(json.dumps({
            "action": "get_option_chains",
            "symbol": "AAPL",
            "contractType": "CALL",
            "strike": 180.0,
            "fromDate": "2023-12-15",
            "use_streaming": False
        }))
        print_response(response)
        
        # Wait a moment for streaming to initialize
        logger.info("\nWaiting for streaming data to initialize...")
        time.sleep(5)
        
        # Example 6: Get streaming option data
        logger.info("\nExample 6: Get streaming option data")
        response = client.send_request(json.dumps({
            "action": "get_option_chains",
            "symbol": "AAPL",
            "contractType": "CALL",
            "strike": 180.0,
            "fromDate": "2023-12-15",
            "use_streaming": True
        }))
        print_response(response)
        
        # Example 7: Using JSON file for streaming quote
        logger.info("\nExample 7: Using JSON file for streaming quote")
        response = client.send_from_file("example_requests/get_streaming_quote.json")
        print_response(response)
        
        # Example 8: Using JSON file for streaming option
        logger.info("\nExample 8: Using JSON file for streaming option")
        response = client.send_from_file("example_requests/get_streaming_option.json")
        print_response(response)

def print_response(response):
    """Print a formatted response."""
    if response.get('success'):
        logger.info("Request successful")
        # Print first part of data to avoid overwhelming output
        data = response.get('data', {})
        if data:
            # Check if data is from streaming
            source = data.get('source', 'API')
            if source == 'streaming':
                logger.info("Data source: STREAMING")
            else:
                logger.info("Data source: API")
                
            # Print first 500 chars of the data
            logger.info(f"Data: {json.dumps(data, indent=2)[:500]}...")
        
        # Print message if available
        if 'message' in response:
            logger.info(f"Message: {response['message']}")
    else:
        logger.error(f"Request failed: {response.get('error')}")

if __name__ == "__main__":
    main()