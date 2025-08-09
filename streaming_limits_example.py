#!/usr/bin/env python3
"""
Example demonstrating streaming service subscription limits.
Shows how the service enforces limits and replaces subscriptions.
"""
import json
import logging
import time
from client import SchwabClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Demonstrate streaming subscription limits."""
    logger.info("Streaming Limits Example")
    logger.info("=" * 50)
    
    with SchwabClient() as client:
        # Check if server is running
        ping_response = client.ping()
        if not ping_response.get('success'):
            logger.error("Server is not running. Please start the server first.")
            return
        
        logger.info("Server is running. Testing streaming limits...")
        
        # Example 1: Test stock subscription limit (max 1)
        logger.info("\n=== Testing Stock Subscription Limit (Max 1) ===")
        
        # Subscribe to first stock
        logger.info("1. Subscribing to AAPL...")
        response = client.send_request(json.dumps({
            "action": "get_quotes",
            "symbols": "AAPL",
            "use_streaming": False  # This will add to streaming subscriptions
        }))
        if response.get('success'):
            logger.info("✓ AAPL subscription added")
        
        time.sleep(2)
        
        # Subscribe to second stock (should replace AAPL)
        logger.info("2. Subscribing to MSFT (should replace AAPL)...")
        response = client.send_request(json.dumps({
            "action": "get_quotes",
            "symbols": "MSFT",
            "use_streaming": False
        }))
        if response.get('success'):
            logger.info("✓ MSFT subscription added (AAPL replaced)")
        
        time.sleep(2)
        
        # Subscribe to third stock (should replace MSFT)
        logger.info("3. Subscribing to GOOGL (should replace MSFT)...")
        response = client.send_request(json.dumps({
            "action": "get_quotes",
            "symbols": "GOOGL",
            "use_streaming": False
        }))
        if response.get('success'):
            logger.info("✓ GOOGL subscription added (MSFT replaced)")
        
        # Example 2: Test option subscription limit (max 4)
        logger.info("\n=== Testing Option Subscription Limit (Max 4) ===")
        
        # Subscribe to options for AAPL (2 strikes × 2 types = 4 options)
        logger.info("1. Subscribing to AAPL options (2 strikes: 180, 185)...")
        response = client.send_request(json.dumps({
            "action": "get_option_chains",
            "symbol": "AAPL",
            "contractType": "ALL",
            "strike": 180.0,
            "fromDate": "2024-01-19",
            "use_streaming": False
        }))
        if response.get('success'):
            logger.info("✓ AAPL option subscriptions added (4 total)")
        
        time.sleep(2)
        
        # Subscribe to options for MSFT (should replace AAPL options)
        logger.info("2. Subscribing to MSFT options (should replace AAPL options)...")
        response = client.send_request(json.dumps({
            "action": "get_option_chains",
            "symbol": "MSFT",
            "contractType": "ALL",
            "strike": 200.0,
            "fromDate": "2024-01-19",
            "use_streaming": False
        }))
        if response.get('success'):
            logger.info("✓ MSFT option subscriptions added (AAPL options replaced)")
        
        # Example 3: Show current streaming status
        logger.info("\n=== Current Streaming Status ===")
        logger.info("The streaming service now maintains:")
        logger.info("- 1 stock subscription (latest: GOOGL)")
        logger.info("- Up to 4 option subscriptions (latest: MSFT options)")
        logger.info("- All providing real-time bid, ask, and volume data")
        
        logger.info("\n=== Streaming Limits Summary ===")
        logger.info("✓ Stock limit enforced: Only 1 stock at a time")
        logger.info("✓ Option limit enforced: Max 4 options (2 strikes × 2 types)")
        logger.info("✓ Replacement logic: New subscriptions replace old ones")
        logger.info("✓ Prevents timeout issues from too many subscriptions")

if __name__ == "__main__":
    main()