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

def format_price(price):
    """Formats a price to two decimal places with a leading zero."""
    return f"{price:.2f}"

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

def find_replacement_order(client, account_hash, original_order_id, instrument_details):
    """
    Find the new order that replaced an old one.
    It looks for a working order with the same instrument details but a different order ID.
    """
    print(f"\nSearching for replacement of order {original_order_id}...")

    working_statuses_to_check = ['WORKING', 'PENDING_ACTIVATION']
    all_working_orders = []

    for status in working_statuses_to_check:
        orders_response = client.get_option_orders(account_id=account_hash, status=status, max_results=50)
        if orders_response.get('success'):
            all_working_orders.extend(orders_response.get('data', []))
        else:
            print(f"\nWarning: Could not retrieve orders with status '{status}'.")

    if not all_working_orders:
        print("No working orders found to search for replacement.")
        return None

    # Details from the original instrument
    symbol = instrument_details['symbol']
    option_type_full = instrument_details['put_call']
    strike_price = instrument_details['strike']
    expiry_date = instrument_details['expiry']

    for order in all_working_orders:
        if str(order.get('orderId')) == str(original_order_id):
            continue # Skip the original order

        for leg in order.get('orderLegCollection', []):
            instrument = leg.get('instrument', {})
            if instrument.get('assetType') == 'OPTION':
                try:
                    # Direct comparison using structured data first
                    if (instrument.get('underlyingSymbol') == symbol and
                        instrument.get('putCall') == option_type_full and
                        abs(instrument.get('strikePrice') - strike_price) < 0.001):

                        # Description parsing for expiry is still needed as a fallback/check
                        desc_expiry = None
                        desc_parts = instrument.get('description', '').split(' ')
                        if len(desc_parts) > 2:
                            desc_expiry_str = desc_parts[-3]
                            desc_expiry = datetime.strptime(desc_expiry_str, '%m/%d/%Y').strftime('%Y-%m-%d')

                        if desc_expiry and desc_expiry == expiry_date:
                             print(f"Found replacement order: {order.get('orderId')} with status {order.get('status')}")
                             return order

                except (ValueError, IndexError, KeyError):
                    continue

    print("No replacement order found.")
    return None

def poll_order_status(client, account_hash, order_id):
    """Poll the status of an order until it is filled, canceled, or replaced."""
    print("\nMonitoring order status...", end="", flush=True)

    # Get initial order details to extract instrument info for periodic updates
    initial_details_response = client.get_option_order_details(account_id=account_hash, order_id=order_id)
    if not initial_details_response.get('success'):
        print(f"\nError getting initial order details: {initial_details_response.get('error')}")
        return None, "ERROR"

    initial_order_details = initial_details_response.get('data', {})

    # Prepare details for periodic updates
    order_summary, instrument_details = None, None
    try:
        leg = initial_order_details.get('orderLegCollection', [{}])[0]
        instrument = leg.get('instrument', {})
        symbol = instrument.get('underlyingSymbol')
        put_call = instrument.get('putCall')
        strike_price = instrument.get('strikePrice')
        desc_parts = instrument.get('description', '').split(' ')
        expiry_str = desc_parts[-3]
        expiry_date = datetime.strptime(expiry_str, '%m/%d/%Y').strftime('%Y-%m-%d')

        instrument_details = {
            "symbol": symbol, "put_call": put_call, "strike": strike_price, "expiry": expiry_date
        }

        order_summary = (f"{leg.get('instruction', '').replace('_', ' ')} {int(leg.get('quantity', 0))} "
                         f"{put_call.lower()} strike {format_price(strike_price)} "
                         f"with limit price {format_price(initial_order_details.get('price'))}")
    except (ValueError, IndexError, KeyError) as e:
        print(f"\nWarning: Could not parse all order details for periodic updates: {e}")
        order_summary = f"Order ID {order_id}"

    poll_count = 0
    while True:
        # The first output will be a dot, subsequent ones will be on new lines if needed
        if poll_count > 0:
             print(".", end="", flush=True)
        time.sleep(4)
        poll_count += 1

        order_details_response = client.get_option_order_details(account_id=account_hash, order_id=order_id)

        if not order_details_response.get('success'):
            print(f"\nError getting order details: {order_details_response.get('error')}")
            return None, "ERROR"

        order_details = order_details_response.get('data', {})
        status = order_details.get('status')

        if status == 'FILLED':
            print("\nOrder filled!")
            return order_details, "FILLED"
        elif status == 'REPLACED':
            print(f"\nOrder {order_id} has been replaced.")
            if not instrument_details:
                print("\nCannot find replacement without instrument details. Restarting flow.")
                return None, "REPLACEMENT_NOT_FOUND"

            replacement_order = find_replacement_order(client, account_hash, order_id, instrument_details)
            if replacement_order:
                new_order_id = replacement_order.get('orderId')
                print(f"Now monitoring new order {new_order_id}.")
                order_id = new_order_id
                poll_count = 0 # Reset poll count for the new order

                # Update order summary for periodic updates
                try:
                    leg = replacement_order.get('orderLegCollection', [{}])[0]
                    instrument = leg.get('instrument', {})
                    order_summary = (f"{leg.get('instruction', '').replace('_', ' ')} {int(leg.get('quantity', 0))} "
                                     f"{instrument.get('putCall').lower()} strike {format_price(instrument.get('strikePrice'))} "
                                     f"with limit price {format_price(replacement_order.get('price'))}")
                except Exception as e:
                    print(f"\nWarning: Could not parse new order details for periodic updates: {e}")
                    order_summary = f"Order ID {new_order_id}"

                continue # Continue the loop to poll the new order immediately
            else:
                print("Could not find replacement order. Restarting flow.")
                return None, "REPLACEMENT_NOT_FOUND"
        elif status in ['CANCELED', 'EXPIRED', 'REJECTED']:
            print(f"\nOrder not filled. Status: {status}")
            return order_details, status

        if poll_count % 4 == 0 and instrument_details:
            try:
                option_chain_response = client.get_option_chains(
                    symbol=instrument_details['symbol'],
                    strike=instrument_details['strike'],
                    fromDate=instrument_details['expiry'],
                    toDate=instrument_details['expiry'],
                    contractType='ALL'
                )

                if option_chain_response.get('success') and option_chain_response.get('data'):
                    oc_data = option_chain_response['data']
                    map_key = 'callExpDateMap' if instrument_details['put_call'] == "CALL" else 'putExpDateMap'
                    date_key = next((k for k in oc_data.get(map_key, {}) if k.startswith(instrument_details['expiry'])), None)
                    if date_key:
                        strike_map = oc_data[map_key].get(date_key, {})
                        option_data = strike_map.get(str(float(instrument_details['strike'])), [None])[0]
                        if option_data:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] {option_data['symbol']} "
                                  f"BID: {format_price(option_data['bid'])} ASK: {format_price(option_data['ask'])} | "
                                  f"Monitoring: {order_summary}")
                        else:
                            print(f"\nCould not find option data for periodic update.")
                else:
                    print(f"\nCould not fetch option chain for periodic update.")
            except Exception as e:
                print(f"\nError during periodic update: {e}")


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
            # The poll_order_status function now handles replaced orders internally.
            # We just need to handle the final status.
            filled_order, status = poll_order_status(client, account_hash, order_id)

            if status == "REPLACEMENT_NOT_FOUND":
                print("Aborting current workflow.")
                return # Exit the workflow, allowing main loop to restart

            if status == "FILLED":
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
                        print(f"Current prices: CALL: {format_price(closing_call_data['bid'])}/{format_price(closing_call_data['ask'])}  PUT: {format_price(closing_put_data['bid'])}/{format_price(closing_put_data['ask'])}")
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
                        filled_closing_order, closing_status = poll_order_status(client, account_hash, closing_order_id)

                        if closing_status == "REPLACEMENT_NOT_FOUND":
                            print("Aborting current workflow.")
                            return

                        if closing_status == "FILLED":
                            # Display summary
                            entry_.get('orderLegCollection', [{}])[0].get('price')
                            exit_price = filled_closing_order.get('orderLegCollection', [{}])[0].get('price')

                            print("\n--- Trade Summary ---")
                            print(f"Action: {side}")
                            print(f"Entry Price: {format_price(entry_price)}")
                            print(f"Exit Action: {closing_side}")
                            print(f"Exit Price: {format_price(exit_price)}")
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
                    print(f"Last price for {symbol}: {format_price(last_price)}")
                except (ValueError, IndexError):
                    print(f"Could not parse last price for {symbol}.")
                    continue

                # Get suggested strike and expiry
                suggested_strike = get_nearest_strike(last_price)
                suggested_expiry = get_next_friday()

                strike_price_str = input(f"Enter strike price (default: {format_price(suggested_strike)}): ")
                strike_price = float(strike_price_str) if strike_price_str else suggested_strike

                expiry_date_str = input(f"Enter option expiry date (YYYY-MM-DD, default: {suggested_expiry}): ")
                expiry_date = expiry_date_str if expiry_date_str else suggested_expiry

                # Display positions
                stock_positions = []
                option_positions = []

                positions_response = client.get_positions_by_symbol(symbol=symbol, account_hash=account_hash)
                if positions_response.get('success') and positions_response.get('data'):
                    data = positions_response.get('data', {})
                    accounts = data.get('accounts', [])
                    for acc in accounts:
                        for pos in acc.get('positions', []):
                            qty = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)

                            if pos.get('assetType') == 'EQUITY':
                                stock_positions.append(f"STOCK: {int(qty)}")
                            elif pos.get('assetType') == 'OPTION':
                                try:
                                    put_call = pos.get('putCall')
                                    description = pos.get('description', '')
                                    desc_parts = description.split(' ')
                                    desc_expiry_str = desc_parts[-3]
                                    desc_strike_str = desc_parts[-2].replace('$', '')

                                    desc_expiry = datetime.strptime(desc_expiry_str, '%m/%d/%Y').strftime('%Y-%m-%d')
                                    desc_strike = float(desc_strike_str)

                                    qty_str = f"+{int(qty)}" if qty > 0 else str(int(qty))

                                    option_positions.append(f"{qty_str} {put_call}; Strike: {desc_strike}; Expiry {desc_expiry}")
                                except (ValueError, IndexError):
                                    option_positions.append(f"{int(qty)} of {description}") # Fallback

                if stock_positions or option_positions:
                    print(f"\n{symbol.upper()} Positions:")
                    for s_pos in stock_positions:
                        print(s_pos)
                    for o_pos in option_positions:
                        print(o_pos)
                else:
                    print("No positions for this symbol in this account.")

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

                call_volume = call_data.get('totalVolume', 0)
                put_volume = put_data.get('totalVolume', 0)
                print(f"CALL:   {format_price(call_data['bid'])}/{format_price(call_data['ask'])}   Volume: {call_volume}        PUT:   {format_price(put_data['bid'])}/{format_price(put_data['ask'])}   Volume: {put_volume}")

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

                price_is_valid = False
                if action == 'B': # Buying
                    if price > 0 and price <= market_ask:
                        price_is_valid = True
                    else:
                        print(f"Invalid price for buy order. Price must be > 0 and <= {format_price(market_ask)}.")
                else: # Selling
                    min_sell_price = market_bid * 0.9
                    if price >= min_sell_price:
                        price_is_valid = True
                    else:
                        print(f"Invalid price for sell order. Price must be >= {format_price(min_sell_price)}.")

                if not price_is_valid:
                    print("Please restart the flow for this symbol.")
                    continue

                quantity = 1

                # Check for existing orders
                existing_order = check_for_existing_order(client, account_hash, symbol, option_type_in, strike_price, expiry_date)

                if existing_order:
                    cancel_and_replace = input("Cancel existing order and place new one? (yes/no): ").lower()
                    if cancel_and_replace == 'yes':
                        existing_order_id = existing_order.get('orderId')
                        print(f"Replacing order {existing_order_id}...")

                        # Determine the side for the replacement order
                        side = "BUY_TO_OPEN" if action == 'B' else ("SELL_TO_CLOSE" if any(p['instrument'].get('symbol') == target_option_data['symbol'] for p in positions_response.get('positions',[])) else "SELL_TO_OPEN")

                        replace_response = client.replace_option_order(
                            account_id=account_hash,
                            order_id=str(existing_order_id),
                            symbol=symbol,
                            option_type="CALL" if option_type_in == 'C' else "PUT",
                            expiration_date=expiry_date,
                            strike_price=strike_price,
                            quantity=1,
                            side=side,
                            order_type="LIMIT",
                            price=price
                        )

                        print_response("Replace Order Result", replace_response)

                        if replace_response.get('success'):
                            print("Order replaced successfully. The new order will be polled.")
                            # After replacing, we need to get the new order ID to poll it.
                            # This is complex as the replace response might not contain the new ID directly.
                            # For now, we will assume the replace action is final and restart the loop.
                            # A more advanced implementation would need to get the new order ID.
                            print("Restarting flow...")
                        else:
                            print(f"Failed to replace order: {replace_response.get('error')}")

                        continue # Always restart the main loop after a replace attempt
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
