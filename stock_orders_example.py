#!/usr/bin/env python3
"""
Example script demonstrating the use of stock order features.
"""
import json
import logging
from client import SchwabClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to demonstrate stock order functionality."""
    logger.info("Schwab API Stock Orders Example")
    logger.info("=" * 50)
    
    # Connect to the server
    with SchwabClient() as client:
        # Check if server is running
        ping_response = client.ping()
        if not ping_response.get('success'):
            logger.error("Server is not running. Please start the server first.")
            return
        
        logger.info("Server is running. Testing stock order functionality...")
        
        # For demonstration purposes, we'll use a placeholder account ID
        # In a real application, you would get this from the get_linked_accounts method
        account_id = "YOUR_ACCOUNT_ID"  # Replace with a real account ID
        
        # Example 1: Place a market order to buy shares
        logger.info("\nExample 1: Place a market order to buy shares")
        response = client.place_stock_order(
            account_id=account_id,
            symbol="AAPL",
            quantity=10,
            side="BUY"
            # Using default MARKET order_type
        )
        print_response(response)
        
        # If the order was successful, save the order ID for later examples
        order_id = None
        if response.get('success') and 'data' in response:
            try:
                # The exact path to the order ID depends on the API response structure
                order_id = response['data'].get('orderId') or response['data'].get('order_id')
                logger.info(f"Saved order ID: {order_id}")
            except (KeyError, AttributeError):
                logger.warning("Could not extract order ID from response")
        
        # Example 2: Place a limit order to sell shares
        logger.info("\nExample 2: Place a limit order to sell shares")
        response = client.place_stock_order(
            account_id=account_id,
            symbol="MSFT",
            quantity=5,
            side="SELL",
            order_type="LIMIT",
            price=350.00,
            duration="DAY"
        )
        print_response(response)
        
        # Example 3: Get all open stock orders
        logger.info("\nExample 3: Get all open stock orders")
        response = client.get_stock_orders(
            account_id=account_id,
            status="OPEN"
        )
        print_response(response)
        
        # Example 4: Get details for a specific order
        if order_id:
            logger.info(f"\nExample 4: Get details for order {order_id}")
            response = client.get_stock_order_details(
                account_id=account_id,
                order_id=order_id
            )
            print_response(response)
        
        # Example 5: Replace (modify) an existing order
        if order_id:
            logger.info(f"\nExample 5: Replace order {order_id}")
            response = client.replace_stock_order(
                account_id=account_id,
                order_id=order_id,
                symbol="AAPL",
                quantity=15,  # Changed from 10 to 15
                side="BUY",
                order_type="LIMIT",
                price=175.00
            )
            print_response(response)
        
        # Example 6: Cancel an order
        if order_id:
            logger.info(f"\nExample 6: Cancel order {order_id}")
            response = client.cancel_stock_order(
                account_id=account_id,
                order_id=order_id
            )
            print_response(response)
        
        # Example 7: Using JSON string
        logger.info("\nExample 7: Place order using JSON string")
        json_request = '''
        {
            "action": "place_stock_order",
            "account_id": "''' + account_id + '''",
            "symbol": "GOOG",
            "quantity": 2,
            "side": "BUY",
            "order_type": "LIMIT",
            "price": 140.00,
            "duration": "DAY"
        }
        '''
        response = client.send_request(json_request)
        print_response(response)
        
        # Example 8: Using JSON file
        logger.info("\nExample 8: Place order using JSON file")
        response = client.send_from_file("example_requests/place_stock_order.json")
        print_response(response)

def print_response(response):
    """Print a formatted response."""
    if response.get('success'):
        logger.info("Request successful")
        # Print first part of data to avoid overwhelming output
        data = response.get('data', {})
        if data:
            # Print first 500 chars of the data
            logger.info(f"Data: {json.dumps(data, indent=2)[:500]}...")
        
        # Print message if available
        if 'message' in response:
            logger.info(f"Message: {response['message']}")
    else:
        logger.error(f"Request failed: {response.get('error')}")

if __name__ == "__main__":
    main()