#!/usr/bin/env python3
"""
Example script demonstrating the use of option order features.
"""
import json
import logging
from datetime import datetime, timedelta
from client import SchwabClient

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def main():
    """Main function to demonstrate option order functionality."""
    logger.info("Schwab API Option Orders Example")
    logger.info("=" * 50)
    
    # Connect to the server
    with SchwabClient() as client:
        # Check if server is running
        ping_response = client.ping()
        if not ping_response.get('success'):
            logger.error("Server is not running. Please start the server first.")
            return
        
        logger.info("Server is running. Testing option order functionality...")
        
        # For demonstration purposes, we'll use a placeholder account ID
        # In a real application, you would get this from the get_linked_accounts method
        account_id = "YOUR_ACCOUNT_ID"  # Replace with a real account ID
        
        # Calculate expiration dates for examples
        today = datetime.now()
        next_month = today + timedelta(days=30)
        next_month_str = next_month.strftime("%Y-%m-%d")
        
        # Example 1: Place a market order to buy call options
        logger.info("\nExample 1: Place a market order to buy call options")
        response = client.place_option_order(
            account_id=account_id,
            symbol="AAPL",
            option_type="CALL",
            expiration_date=next_month_str,
            strike_price=180.00,
            quantity=1,
            side="BUY_TO_OPEN"
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
        
        # Example 2: Place a limit order to sell put options
        logger.info("\nExample 2: Place a limit order to sell put options")
        response = client.place_option_order(
            account_id=account_id,
            symbol="MSFT",
            option_type="PUT",
            expiration_date=next_month_str,
            strike_price=350.00,
            quantity=1,
            side="SELL_TO_OPEN",
            order_type="LIMIT",
            price=5.00,
            duration="DAY"
        )
        print_response(response)
        
        # Example 3: Get all open option orders
        logger.info("\nExample 3: Get all open option orders")
        response = client.get_option_orders(
            account_id=account_id,
            status="OPEN"
        )
        print_response(response)
        
        # Example 4: Get details for a specific option order
        if order_id:
            logger.info(f"\nExample 4: Get details for option order {order_id}")
            response = client.get_option_order_details(
                account_id=account_id,
                order_id=order_id
            )
            print_response(response)
        
        # Example 5: Replace (modify) an existing option order
        if order_id:
            logger.info(f"\nExample 5: Replace option order {order_id}")
            response = client.replace_option_order(
                account_id=account_id,
                order_id=order_id,
                symbol="AAPL",
                option_type="CALL",
                expiration_date=next_month_str,
                strike_price=180.00,
                quantity=2,  # Changed from 1 to 2
                side="BUY_TO_OPEN",
                order_type="LIMIT",
                price=3.50
            )
            print_response(response)
        
        # Example 6: Cancel an option order
        if order_id:
            logger.info(f"\nExample 6: Cancel option order {order_id}")
            response = client.cancel_option_order(
                account_id=account_id,
                order_id=order_id
            )
            print_response(response)
        
        # Example 7: Using JSON string
        logger.info("\nExample 7: Place option order using JSON string")
        json_request = '''
        {
            "action": "place_option_order",
            "account_id": "''' + account_id + '''",
            "symbol": "SPY",
            "option_type": "PUT",
            "expiration_date": "''' + next_month_str + '''",
            "strike_price": 400.00,
            "quantity": 1,
            "side": "BUY_TO_OPEN",
            "order_type": "LIMIT",
            "price": 5.00,
            "duration": "DAY"
        }
        '''
        response = client.send_request(json_request)
        print_response(response)
        
        # Example 8: Using JSON file
        logger.info("\nExample 8: Place option order using JSON file")
        response = client.send_from_file("example_requests/place_option_order.json")
        print_response(response)
        
        # Example 9: Closing an option position
        logger.info("\nExample 9: Closing an option position")
        response = client.place_option_order(
            account_id=account_id,
            symbol="AAPL",
            option_type="CALL",
            expiration_date=next_month_str,
            strike_price=180.00,
            quantity=1,
            side="SELL_TO_CLOSE",
            order_type="MARKET"
        )
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