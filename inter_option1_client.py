import json
import time
from datetime import datetime, timedelta
from client import SchwabClient

def print_response(title: str, response: dict):
    """Helper function to print formatted responses."""
    print(f"\n{'='*50}")
    print(f"{title}")
    print(f"{'='*50}")
    print(json.dumps(response, indent=2))

def get_account_hash(client):
    """Get the first account hash."""
    accounts = client.get_linked_accounts()
    if accounts and accounts.get('success'):
        account_list = accounts.get('data', [])
        if account_list:
            return account_list[0].get('hashValue')
    print("Error: Could not retrieve account hash.")
    return None

def get_nearest_strike(price):
    """Find the nearest strike price."""
    if price < 10:
        return round(price * 2) / 2  # Nearest 0.5
    elif price < 50:
        return round(price)
    elif price < 100:
        return round(price / 2.5) * 2.5 # Nearest 2.5
    else:
        return round(price / 5) * 5 # Nearest 5

def get_next_friday():
    """Get the next upcoming Friday's date."""
    today = datetime.now()
    days_until_friday = (4 - today.weekday() + 7) % 7
    next_friday = today + timedelta(days=days_until_friday)
    return next_friday.strftime('%Y-%m-%d')

def poll_order_status(client, account_hash, order_id):
    """Poll the status of an order until it is filled."""
    print("Monitoring order status...", end="", flush=True)
    while True:
        print(".", end="", flush=True)
        time.sleep(4)

        order_details_response = client.get_option_order_details(account_id=account_hash, order_id=order_id)

        if not order_details_response.get('success'):
            print(f"\nError getting order details: {order_details_response.get('error')}")
            return None

        order_details = order_details_response.get('data', {})
        status = order_details.get('status')

        if status == 'FILLED':
            print("\nOrder filled!")
            return order_details
        elif status in ['CANCELED', 'EXPIRED', 'REJECTED']:
            print(f"\nOrder not filled. Status: {status}")
            return None


def check_for_existing_order(client, account_hash, symbol, option_type, strike_price, expiry_date):
    """Check for existing working orders for the same option by making targeted API calls."""
    print("\nChecking for existing working orders...")

    working_statuses_to_check = ['WORKING', 'PENDING_ACTIVATION']
    all_working_orders = []

    for status in working_statuses_to_check:
        orders_response = client.get_option_orders(account_id=account_hash, status=status, max_results=50)
        if orders_response.get('success'):
            all_working_orders.extend(orders_response.get('data', []))
        else:
            print(f"\nWarning: Could not retrieve orders with status '{status}'.")

    if not all_working_orders:
        print("No working orders found.")
        return None

    # The option_type from user input is 'C' or 'P'. Convert to full name for comparison.
    option_type_full = "CALL" if option_type.upper() == 'C' else "PUT"

    for order in all_working_orders:
        for leg in order.get('orderLegCollection', []):
            instrument = leg.get('instrument', {})

            if instrument.get('assetType') == 'OPTION':
                # Extract details from the instrument object
                underlying = instrument.get('underlyingSymbol')
                put_call = instrument.get('putCall')
                description = instrument.get('description', '')

                # Parse description for strike and expiry
                # Example: "WEBULL CORP 08/15/2025 $15.5 Put"
                try:
                    desc_parts = description.split(' ')
                    desc_expiry_str = desc_parts[-3]
                    desc_strike_str = desc_parts[-2].replace('$', '')

                    desc_expiry = datetime.strptime(desc_expiry_str, '%m/%d/%Y').strftime('%Y-%m-%d')
                    desc_strike = float(desc_strike_str)

                    # Compare the components
                    if (underlying == symbol.upper() and
                        put_call == option_type_full and
                        desc_expiry == expiry_date and
                        abs(desc_strike - strike_price) < 0.001):

                        print(f"Found a matching working order: {order.get('orderId')} with status {order.get('status')}")
                        return order

                except (ValueError, IndexError):
                    # Could not parse this description, skip to the next leg/order.
                    continue

    print("No matching working orders found.")
    return None

def place_order_workflow(client, account_hash, symbol, option_type_in, strike_price, expiry_date, action, price, positions_response, target_option_data):
    """Handles the entire workflow for placing and monitoring an order."""
    quantity = 1

    # Determine side
    side = ""
    if action == 'B':
        side = "BUY_TO_OPEN"
    else: # 'S'
        side = "SELL_TO_CLOSE" if any(p['instrument'].get('symbol') == target_option_data['symbol'] for p in positions_response.get('positions',[])) else "SELL_TO_OPEN"

    # Place opening order
    order_response = client.place_option_order(
        account_id=account_hash,
        symbol=symbol,
        option_type="CALL" if option_type_in == 'C' else "PUT",
        expiration_date=expiry_date,
        strike_price=strike_price,
        quantity=quantity,
        side=side,
        order_type="LIMIT",
        price=price
    )

    print_response("Order Placement Result", order_response)

    if order_response.get('success'):
        order_data = order_response.get('data', {})
        order_id = order_data.get('order_id')

        if order_id:
            filled_order = poll_order_status(client, account_hash, order_id)
            if filled_order:
                # Get the current quote for the option
                print("\nFetching current quote for closing order...")
                closing_option_chain_response = client.get_option_chains(
                    symbol=symbol,
                    strike=strike_price,
                    fromDate=expiry_date,
                    toDate=expiry_date,
                    contractType='ALL'
                )

                if closing_option_chain_response.get('success') and closing_option_chain_response.get('data'):
                    closing_option_data = closing_option_chain_response['data']
                    closing_call_map = closing_option_data.get('callExpDateMap', {})
                    closing_put_map = closing_option_data.get('putExpDateMap', {})

                    closing_call_data = None
                    closing_put_data = None

                    closing_date_key = next((key for key in closing_call_map if key.startswith(expiry_date)), None)
                    if closing_date_key:
                        closing_strike_map_call = closing_call_map.get(closing_date_key, {})
                        closing_call_data = closing_strike_map_call.get(str(float(strike_price)), [None])[0]

                    closing_date_key_put = next((key for key in closing_put_map if key.startswith(expiry_date)), None)
                    if closing_date_key_put:
                        closing_strike_map_put = closing_put_map.get(closing_date_key_put, {})
                        closing_put_data = closing_strike_map_put.get(str(float(strike_price)), [None])[0]

                    if closing_call_data and closing_put_data:
                        print(f"Current prices: CALL: {closing_call_data['bid']}/{closing_call_data['ask']}  PUT: {closing_put_data['bid']}/{closing_put_data['ask']}")
                    else:
                        print("Could not retrieve current prices for closing order.")

                # Prompt for closing price
                closing_price_str = input("Enter limit price for closing order: ")
                try:
                    closing_price = float(closing_price_str)
                except ValueError:
                    print("Invalid price. Aborting closing order.")
                    return

                # Determine closing side
                closing_side = "SELL_TO_CLOSE" if side == "BUY_TO_OPEN" else "BUY_TO_CLOSE"

                # Place closing order
                closing_order_response = client.place_option_order(
                    account_id=account_hash,
                    symbol=symbol,
                    option_type="CALL" if option_type_in == 'C' else "PUT",
                    expiration_date=expiry_date,
                    strike_price=strike_price,
                    quantity=quantity,
                    side=closing_side,
                    order_type="LIMIT",
                    price=closing_price
                )

                print_response("Closing Order Placement Result", closing_order_response)

                if closing_order_response.get('success'):
                    closing_order_data = closing_order_response.get('data', {})
                    closing_order_id = closing_order_data.get('order_id')

                    if closing_order_id:
                        filled_closing_order = poll_order_status(client, account_hash, closing_order_id)
                        if filled_closing_order:
                            # Display summary
                            entry_price = filled_order.get('orderLegCollection', [{}])[0].get('price')
                            exit_price = filled_closing_order.get('orderLegCollection', [{}])[0].get('price')

                            print("\n--- Trade Summary ---")
                            print(f"Action: {side}")
                            print(f"Entry Price: {entry_price}")
                            print(f"Exit Action: {closing_side}")
                            print(f"Exit Price: {exit_price}")
                            print("--------------------")

def main():
    """Main function for the interactive option client."""
    print("Schwab Interactive Option Client")
    print("Make sure the server is running before executing this script!")

    with SchwabClient() as client:
        account_hash = get_account_hash(client)
        if not account_hash:
            return

        print(f"Using account hash: {account_hash}")

        while True:
            try:
                symbol = input("\nEnter a stock symbol (or 'quit' to exit): ").upper()
                if symbol == 'QUIT':
                    break

                # Get last price
                quotes_response = client.get_quotes(symbols=[symbol])
                if not quotes_response.get('success') or not quotes_response.get('data'):
                    print(f"Could not retrieve quote for {symbol}.")
                    continue

                # The data is a list of strings, get the first one
                quote_string = quotes_response['data'][0]
                parts = quote_string.split()

                # Expected format: symbol lastPrice bidPrice askPrice totalVolume
                if len(parts) < 2 or parts[0] != symbol:
                    print(f"Unexpected quote format for {symbol}.")
                    continue

                try:
                    last_price = float(parts[1])
                    print(f"Last price for {symbol}: {last_price}")
                except (ValueError, IndexError):
                    print(f"Could not parse last price for {symbol}.")
                    continue

                # Get suggested strike and expiry
                suggested_strike = get_nearest_strike(last_price)
                suggested_expiry = get_next_friday()

                strike_price_str = input(f"Enter strike price (default: {suggested_strike}): ")
                strike_price = float(strike_price_str) if strike_price_str else suggested_strike

                expiry_date_str = input(f"Enter option expiry date (YYYY-MM-DD, default: {suggested_expiry}): ")
                expiry_date = expiry_date_str if expiry_date_str else suggested_expiry

                # Get option chain
                option_chain_response = client.get_option_chains(
                    symbol=symbol,
                    strike=strike_price,
                    fromDate=expiry_date,
                    toDate=expiry_date,
                    contractType='ALL'
                )

                if not option_chain_response.get('success') or not option_chain_response.get('data'):
                    print(f"Could not retrieve option chain: {option_chain_response.get('error')}")
                    continue

                option_chain_data = option_chain_response.get('data', {})
                call_map = option_chain_data.get('callExpDateMap', {})
                put_map = option_chain_data.get('putExpDateMap', {})

                call_data = None
                put_data = None

                # Find the correct date key
                date_key = next((key for key in call_map if key.startswith(expiry_date)), None)
                if date_key:
                    strike_map_call = call_map.get(date_key, {})
                    call_data = strike_map_call.get(str(float(strike_price)), [None])[0]

                date_key_put = next((key for key in put_map if key.startswith(expiry_date)), None)
                if date_key_put:
                    strike_map_put = put_map.get(date_key_put, {})
                    put_data = strike_map_put.get(str(float(strike_price)), [None])[0]

                if not call_data or not put_data:
                    print("Could not find option data for the specified strike and date.")
                    continue

                print(f"CALL:   {call_data['bid']}/{call_data['ask']}  PUT: {put_data['bid']}/{put_data['ask']}")

                # Display positions
                positions_response = client.get_positions_by_symbol(symbol=symbol, account_hash=account_hash)
                if positions_response.get('success') and positions_response.get('positions'):
                    positions = positions_response.get('positions')
                    position_strings = []
                    for pos in positions:
                        qty = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
                        desc = pos.get('instrument', {}).get('description', 'Unknown')
                        position_strings.append(f"{qty} of {desc}")
                    if position_strings:
                        print(f"Positions: {'; '.join(position_strings)}")
                else:
                    print("No positions for this symbol in this account.")

                # Prompt for action
                action_input = input("ACTION- ").upper().strip()
                parts = action_input.split()
                if len(parts) != 3:
                    print("Invalid action format. Use: B/S C/P PRICE (e.g., B C 1.25)")
                    continue

                action, option_type_in, price_str = parts

                if action not in ['B', 'S']:
                    print("Invalid action. Must be 'B' (buy) or 'S' (sell).")
                    continue

                if option_type_in not in ['C', 'P']:
                    print("Invalid option type. Must be 'C' (call) or 'P' (put).")
                    continue

                try:
                    price = float(price_str)
                except ValueError:
                    print("Invalid price. Must be a number.")
                    continue

                # Price validation
                target_option_data = call_data if option_type_in == 'C' else put_data
                market_bid = target_option_data['bid']
                market_ask = target_option_data['ask']

                price_too_far = False
                if action == 'B': # Buying
                    if market_ask > 0 and price > market_ask * 1.5:
                        price_too_far = True
                else: # Selling
                    if market_bid > 0 and price < market_bid * 0.5:
                        price_too_far = True

                if price_too_far:
                    print("Price difference too high and rejected.")
                    continue

                quantity = 1

                # Check for existing orders
                existing_order = check_for_existing_order(client, account_hash, symbol, option_type_in, strike_price, expiry_date)

                if existing_order:
                    cancel_and_replace = input("Cancel existing order and place new one? (yes/no): ").lower()
                    if cancel_and_replace == 'yes':
                        existing_order_id = existing_order.get('orderId')
                        print(f"Canceling order {existing_order_id}...")
                        cancel_response = client.cancel_option_order(account_id=account_hash, order_id=existing_order_id)
                        if cancel_response.get('success'):
                            print("Existing order canceled successfully.")
                            place_order_workflow(client, account_hash, symbol, option_type_in, strike_price, expiry_date, action, price, positions_response, target_option_data)
                        else:
                            print(f"Failed to cancel existing order: {cancel_response.get('error')}")
                            print("Aborting new order placement.")
                            continue
                    else:
                        continue_anyway = input("Continue and place new order anyway? (c to continue, any other key to exit): ").lower()
                        if continue_anyway == 'c':
                            place_order_workflow(client, account_hash, symbol, option_type_in, strike_price, expiry_date, action, price, positions_response, target_option_data)
                        else:
                            print("Aborting order.")
                            continue
                else:
                    place_order_workflow(client, account_hash, symbol, option_type_in, strike_price, expiry_date, action, price, positions_response, target_option_data)
            except KeyboardInterrupt:
                print("\nClient interrupted by user.")
                break
            except Exception as e:
                print(f"\nAn error occurred: {e}")
                continue

    print("\nClient disconnected.")

if __name__ == "__main__":
    main()
