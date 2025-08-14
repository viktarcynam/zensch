import json
import sys
import select
import termios
import tty
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
    """Formats a price to two decimal places with a leading zero. Handles None safely."""
    if price is None:
        return "N/A"
    return f"{price:.2f}"

def parse_option_symbol(symbol_string):
    """
    Parses a standard OCC option symbol string.
    Example: 'HOG   250815C00024000'
    Returns: A dictionary with 'underlying', 'expiry_date', 'put_call', 'strike'.
    """
    try:
        underlying = symbol_string[0:6].strip()
        date_str = symbol_string[6:12]
        expiry_date = datetime.strptime(date_str, '%y%m%d').strftime('%Y-%m-%d')
        put_call = "CALL" if symbol_string[12] == 'C' else "PUT"
        strike_int = int(symbol_string[13:])
        strike = float(strike_int) / 1000.0

        return {
            "underlying": underlying,
            "expiry_date": expiry_date,
            "put_call": put_call,
            "strike": strike
        }
    except (ValueError, IndexError) as e:
        print(f"\nError parsing OCC symbol '{symbol_string}': {e}")
        return None

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


def parse_option_position_details(position: dict) -> dict or None:
    """
    Parses an option position object to extract key details.
    The description string is parsed for strike and expiry.
    Returns a dictionary with details, or None on failure.
    """
    try:
        if position.get('assetType') != 'OPTION':
            return None

        description = position.get('description', '')
        # Example: "WEBULL CORP 08/15/2025 $15.5 Put"
        desc_parts = description.split(' ')
        desc_expiry_str = desc_parts[-3]
        desc_strike_str = desc_parts[-2].replace('$', '')

        desc_expiry = datetime.strptime(desc_expiry_str, '%m/%d/%Y').strftime('%Y-%m-%d')
        desc_strike = float(desc_strike_str)

        quantity = position.get('longQuantity', 0) - position.get('shortQuantity', 0)

        return {
            "put_call": position.get('putCall'),
            "strike": desc_strike,
            "expiry": desc_expiry,
            "quantity": quantity
        }
    except (ValueError, IndexError, TypeError):
        return None

def find_replacement_order(client, account_hash, original_order):
    """
    Find the new order that replaced an old one.
    It looks for a working order with the same instrument details and instruction.
    Includes a retry mechanism to handle backend processing delays.
    """
    original_order_id = original_order['orderId']
    print(f"\nSearching for replacement of order {original_order_id}...")

    max_retries = 3
    retry_delay = 2 # seconds

    for attempt in range(max_retries):
        if attempt > 0:
            print(f"Retrying search... (Attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)

        working_statuses_to_check = ['WORKING', 'PENDING_ACTIVATION', 'ACCEPTED', 'QUEUED']
        all_working_orders = []

        for status in working_statuses_to_check:
            orders_response = client.get_option_orders(account_id=account_hash, status=status, max_results=50)
            if orders_response.get('success'):
                all_working_orders.extend(orders_response.get('data', []))
            else:
                print(f"\nWarning: Could not retrieve orders with status '{status}'.")

        if not all_working_orders:
            if attempt < max_retries - 1:
                continue # Go to next retry attempt
            else:
                print("No working orders found to search for replacement after multiple attempts.")
                return None

        # Search for the matching order in the retrieved list
        for order in all_working_orders:
            if str(order.get('orderId')) == str(original_order_id):
                continue

            for leg in order.get('orderLegCollection', []):
                instrument = leg.get('instrument', {})
                if instrument.get('assetType') == 'OPTION':

                    candidate_details = parse_option_symbol(instrument.get('symbol'))
                    if not candidate_details:
                        continue

                    # Compare all key details. Price is expected to be different.
                    if (candidate_details['underlying'] == original_order['symbol'] and
                        candidate_details['put_call'] == original_order['putCall'] and
                        leg.get('instruction') == original_order['instruction'] and
                        abs(candidate_details['strike'] - original_order['strike']) < 0.001 and
                        candidate_details['expiry_date'] == original_order['expiry']):

                        print(f"Found replacement order: {order.get('orderId')} with status {order.get('status')}")
                        return order

        # If no match was found in this attempt's list of orders, the loop will either retry or exit.

    print("No replacement order found after multiple attempts.")
    return None

def display_symbol_positions(client, account_hash, symbol, filled_instrument_details):
    """
    Fetches, sorts, and displays all option positions for a given underlying symbol.
    """
    print(f"\nCurrent Position: {symbol.upper()}")
    time.sleep(1) # Delay for backend update

    all_positions_response = client.get_positions(account_hash=account_hash)
    if not (all_positions_response.get('success') and all_positions_response.get('data')):
        print("Could not retrieve positions.")
        return

    all_option_positions = []
    accounts = all_positions_response.get('data', {}).get('accounts', [])
    for acc in accounts:
        for pos in acc.get('positions', []):
            # We only care about options for the relevant symbol
            if pos.get('instrument', {}).get('underlyingSymbol') == symbol.upper():
                pos_details = parse_option_position_details(pos)
                if pos_details:
                    all_option_positions.append(pos_details)

    if not all_option_positions:
        print("No option positions found for this symbol.")
        return

    # Separate the just-filled instrument from the rest
    just_filled_position = None
    other_positions = []

    for pos in all_option_positions:
        is_match = (pos['put_call'] == filled_instrument_details['putCall'] and
                    abs(pos['strike'] - filled_instrument_details['strike']) < 0.001 and
                    pos['expiry'] == filled_instrument_details['expiry'])
        if is_match:
            just_filled_position = pos
        else:
            other_positions.append(pos)

    # Sort the other positions
    other_positions.sort(key=lambda p: (p['expiry'], p['strike']))

    # Function to format a single position line
    def format_pos_line(p):
        qty = p['quantity']
        if qty == 0: return None # Don't print flat positions

        long_short = "long" if qty > 0 else "short"
        abs_qty = abs(int(qty))
        return (f"{long_short} {abs_qty} {p['put_call']} "
                f"Strike:{format_price(p['strike'])} Expiry:{p['expiry']}")

    # Print the just-filled position first, if it exists and is not flat
    if just_filled_position:
        line = format_pos_line(just_filled_position)
        if line:
            print(line)
    else:
         print(f"Warning: Could not find the specific position for the just-filled order.")


    # Print the rest of the sorted positions
    for pos in other_positions:
        line = format_pos_line(pos)
        if line:
            print(line)

def poll_order_status(client, account_hash, order_to_monitor):
    """
    Poll the status of an order until it is filled, canceled, or replaced.
    Relies on a passed-in dictionary of order details.
    Also listens for user input to adjust ('a') or cancel ('q') the order.
    """
    old_settings = termios.tcgetattr(sys.stdin)
    try:
        tty.setcbreak(sys.stdin.fileno())
        print("\nMonitoring order status... Press 'A' to adjust price, 'Q' to cancel.", end="", flush=True)

        current_order_id = order_to_monitor['orderId']
        order_summary = (f"{order_to_monitor['instruction'].replace('_', ' ')} {int(order_to_monitor['quantity'])} "
                         f"{order_to_monitor['putCall'].lower()} strike {format_price(order_to_monitor['strike'])} "
                         f"with limit price {format_price(order_to_monitor['price'])}")

        poll_count = 0
        next_poll_time = time.time()

        while True:
            wait_time = max(0, next_poll_time - time.time())
            rlist, _, _ = select.select([sys.stdin], [], [], wait_time)

            if rlist:
                char = sys.stdin.read(1) # Case-sensitive
                if char == 'A':
                    # Restore terminal for standard input
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

                    print("\n\n--- Adjust Order ---")
                    print(f"Current Order: {order_summary}")

                    # 1. Fetch current quote
                    print("Fetching latest quote...")
                    latest_quote_response = client.get_option_chains(
                        symbol=order_to_monitor['symbol'],
                        strike=order_to_monitor['strike'],
                        fromDate=order_to_monitor['expiry'],
                        toDate=order_to_monitor['expiry'],
                        contractType=order_to_monitor['putCall']
                    )

                    market_bid = None
                    market_ask = None
                    option_list_data = None
                    if latest_quote_response.get('success') and latest_quote_response.get('data'):
                        oc_data = latest_quote_response['data']
                        is_call = order_to_monitor['putCall'] == 'CALL'
                        exp_map = oc_data.get('callExpDateMap' if is_call else 'putExpDateMap', {})
                        date_key = next((k for k in exp_map if k.startswith(order_to_monitor['expiry'])), None)
                        if date_key:
                            strike_map = exp_map.get(date_key, {})
                            option_list_data = strike_map.get(str(float(order_to_monitor['strike'])), [None])[0]
                            if option_list_data:
                                market_bid = option_list_data.get('bid')
                                market_ask = option_list_data.get('ask')
                                print(f"Current Market: Bid: {format_price(market_bid)} / Ask: {format_price(market_ask)}")

                    if market_bid is None or market_ask is None:
                        print("Could not retrieve current market price. Cannot perform price validation. Aborting adjustment.")
                        tty.setcbreak(sys.stdin.fileno())
                        print("\nResuming monitoring...", end="", flush=True)
                        continue

                    # Loop for new price input and validation
                    while True:
                        new_price_str = input("Enter new limit price, relative adjustment (e.g., +5), or 'c' to cancel: ").strip()

                        if not new_price_str or new_price_str.lower() == 'c':
                            print("Adjustment cancelled.")
                            break

                        new_price = None
                        try:
                            if new_price_str.startswith('+') or new_price_str.startswith('-'):
                                adjustment = float(new_price_str) * 0.01
                                new_price = round(order_to_monitor['price'] + adjustment, 2)
                            else:
                                new_price = float(new_price_str)
                        except (ValueError, TypeError):
                            print("Invalid input. Please enter a number, a relative adjustment like '+5', or 'c'.")
                            continue

                        if new_price <= 0:
                            print(f"Invalid price. New price must be positive. You entered: {format_price(new_price)}")
                            continue

                        is_buy_order = "BUY" in order_to_monitor['instruction']
                        if is_buy_order:
                            if new_price > market_ask:
                                print(f"Invalid price for buy order. Price ({format_price(new_price)}) cannot be higher than ask ({format_price(market_ask)}).")
                                continue
                        else:
                            if new_price < market_bid:
                                print(f"Invalid price for sell order. Price ({format_price(new_price)}) cannot be lower than bid ({format_price(market_bid)}).")
                                continue

                        # Re-calculate side based on current positions
                        action = 'B' if is_buy_order else 'S'
                        positions_response = client.get_positions_by_symbol(symbol=order_to_monitor['symbol'], account_hash=account_hash)
                        current_quantity = 0
                        if positions_response.get('success') and positions_response.get('data'):
                            accounts = positions_response.get('data', {}).get('accounts', [])
                            for acc in accounts:
                                for pos in acc.get('positions', []):
                                    if pos.get('instrument', {}).get('symbol') == option_list_data.get('symbol'):
                                        current_quantity = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
                                        break
                                if current_quantity != 0:
                                    break

                        side = ""
                        if action == 'B':
                            side = "BUY_TO_CLOSE" if current_quantity < 0 else "BUY_TO_OPEN"
                        else:  # 'S'
                            side = "SELL_TO_CLOSE" if current_quantity > 0 else "SELL_TO_OPEN"

                        print(f"New price {format_price(new_price)} is valid. Replacing order with side '{side}'...")

                        replace_response = client.replace_option_order(
                            account_id=account_hash,
                            order_id=str(current_order_id),
                            symbol=order_to_monitor['symbol'],
                            option_type=order_to_monitor['putCall'],
                            expiration_date=order_to_monitor['expiry'],
                            strike_price=order_to_monitor['strike'],
                            quantity=order_to_monitor['quantity'],
                            side=side,
                            order_type="LIMIT",
                            price=new_price
                        )

                        print_response("Replace Order Result", replace_response)
                        if replace_response.get('success'):
                            # Extract the new order ID from the successful response
                            new_order_id = replace_response.get('data', {}).get('new_order_id')
                            if new_order_id:
                                print(f"Order replace successful. Now monitoring new order ID: {new_order_id}")
                                # --- UPDATE STATE TO MONITOR THE NEW ORDER ---
                                current_order_id = new_order_id
                                order_to_monitor['orderId'] = new_order_id
                                order_to_monitor['price'] = new_price
                                order_to_monitor['instruction'] = side # Update instruction based on new side

                                # Rebuild the summary string for display
                                order_summary = (f"{order_to_monitor['instruction'].replace('_', ' ')} {int(order_to_monitor['quantity'])} "
                                                 f"{order_to_monitor['putCall'].lower()} strike {format_price(order_to_monitor['strike'])} "
                                                 f"with limit price {format_price(order_to_monitor['price'])}")
                                poll_count = 0 # Reset poll counter for the new order
                            else:
                                # This case handles if the server response changes format unexpectedly
                                print("WARNING: Replacement reported success, but no new order ID was returned. The app may not track the new order correctly.")
                        else:
                            print(f"Failed to replace order: {replace_response.get('error')}")

                        break

                    # Set terminal back to cbreak mode for polling
                    tty.setcbreak(sys.stdin.fileno())
                    print("\nResuming monitoring...", end="", flush=True)
                elif char == 'Q':
                    # Restore terminal for standard input
                    termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)

                    # Check for existing positions before confirming cancel
                    print("\nChecking for existing positions for this instrument...")
                    positions_response = client.get_positions_by_symbol(symbol=order_to_monitor['symbol'], account_hash=account_hash)
                    found_position = False
                    if positions_response.get('success') and positions_response.get('data'):
                        accounts = positions_response.get('data', {}).get('accounts', [])
                        for acc in accounts:
                            for pos in acc.get('positions', []):
                                pos_details = parse_option_position_details(pos)
                                if not pos_details:
                                    continue

                                # Check if position matches the order being cancelled
                                if (pos_details['put_call'] == order_to_monitor['putCall'] and
                                    abs(pos_details['strike'] - order_to_monitor['strike']) < 0.001 and
                                    pos_details['expiry'] == order_to_monitor['expiry']):

                                    if pos_details['quantity'] != 0:
                                        qty_str = f"+{int(pos_details['quantity'])}" if pos_details['quantity'] > 0 else str(int(pos_details['quantity']))
                                        print("\n" + "="*20 + " WARNING " + "="*20)
                                        print(f"  You have an existing position of {qty_str} contracts for this option.")
                                        print("  Cancelling this order may leave the position open.")
                                        print("="*49)
                                        found_position = True
                                        break
                            if found_position:
                                break

                    if not found_position:
                        print("No existing position found for this instrument.")

                    try:
                        confirm = input("\nAre you sure you want to cancel this order? (y/n): ").lower()
                        if confirm == 'y':
                            print("Cancelling order...")
                            cancel_response = client.cancel_option_order(
                                account_id=account_hash,
                                order_id=current_order_id
                            )
                            print_response("Cancel Order Result", cancel_response)
                            if cancel_response.get('success'):
                                print("Order cancelled successfully. Returning to main menu.")
                                return None, 'CANCELED' # Exit the poll loop
                            else:
                                print(f"Failed to cancel order: {cancel_response.get('error')}")
                        else:
                            print("Cancellation aborted.")
                    except Exception as e:
                        print(f"An error occurred during cancellation: {e}")

                    # Set terminal back to cbreak mode
                    tty.setcbreak(sys.stdin.fileno())
                    print("\nResuming monitoring...", end="", flush=True)

            if time.time() < next_poll_time:
                continue

            next_poll_time = time.time() + 2
            if poll_count > 0:
                print(".", end="", flush=True)
            poll_count += 1

            order_details_response = client.get_option_order_details(account_id=account_hash, order_id=current_order_id)

            if not order_details_response.get('success'):
                print(f"\nError getting order details for order {current_order_id}: {order_details_response.get('error')}")
                return None, "ERROR"

            order_details = order_details_response.get('data', {})
            status = order_details.get('status')

            if status == 'FILLED':
                print("\nOrder filled!")
                # --- BEGIN DEBUG CODE ---
                try:
                    order_id_for_file = order_details.get('orderId', 'unknown_order')
                    # Save order details
                    details_filename = f"filled_order_details_{order_id_for_file}.json"
                    with open(details_filename, 'w') as f:
                        json.dump(order_details, f, indent=2)
                    print(f"DEBUG: Saved filled order details to {details_filename}")

                    # Save position details
                    positions_response = client.get_positions(account_hash=account_hash)
                    if positions_response.get('success'):
                        positions_filename = f"positions_at_fill_{order_id_for_file}.json"
                        with open(positions_filename, 'w') as f:
                            json.dump(positions_response.get('data', {}), f, indent=2)
                        print(f"DEBUG: Saved position details to {positions_filename}")
                    else:
                        print("DEBUG: Could not fetch position details at time of fill.")

                except Exception as e:
                    print(f"DEBUG: An error occurred during debug file generation: {e}")
                # --- END DEBUG CODE ---

                # --- BEGIN POSITION DISPLAY ---
                display_symbol_positions(client, account_hash, order_to_monitor['symbol'], order_to_monitor)
                # --- END POSITION DISPLAY ---

                return order_details, "FILLED"
            elif status == 'REPLACED':
                print(f"\nOrder {current_order_id} has been replaced.")
                replacement_order = find_replacement_order(client, account_hash, order_to_monitor)
                if replacement_order:
                    new_order_id = replacement_order.get('orderId')
                    print(f"Now monitoring new order {new_order_id}.")
                    current_order_id = new_order_id
                    order_to_monitor['orderId'] = new_order_id
                    try:
                        new_leg = replacement_order.get('orderLegCollection', [{}])[0]
                        order_to_monitor['price'] = replacement_order.get('price')
                        order_to_monitor['instruction'] = new_leg.get('instruction')
                        order_to_monitor['quantity'] = new_leg.get('quantity')
                        order_summary = (f"{order_to_monitor['instruction'].replace('_', ' ')} {int(order_to_monitor['quantity'])} "
                                         f"{order_to_monitor['putCall'].lower()} strike {format_price(order_to_monitor['strike'])} "
                                         f"with limit price {format_price(order_to_monitor['price'])}")
                    except Exception as e:
                        print(f"\nWarning: Could not parse all new order details for periodic updates: {e}")
                        order_summary = f"Order ID {new_order_id}"
                    poll_count = 0
                    continue
                else:
                    print("\nCould not find a new working replacement order. Checking if the original order was filled instead...")
                    time.sleep(1) # Give a moment for the account to update
                    original_order_details_response = client.get_option_order_details(account_id=account_hash, order_id=order_to_monitor['orderId'])

                    if original_order_details_response.get('success'):
                        original_order_details = original_order_details_response.get('data', {})
                        if original_order_details.get('status') == 'FILLED':
                            print("Original order was filled before replacement could complete. Verifying position...")

                            # Verify the position exists
                            positions_response = client.get_positions_by_symbol(symbol=order_to_monitor['symbol'], account_hash=account_hash)
                            position_verified = False
                            if positions_response.get('success') and positions_response.get('data'):
                                accounts = positions_response.get('data', {}).get('accounts', [])
                                for acc in accounts:
                                    for pos in acc.get('positions', []):
                                        pos_details = parse_option_position_details(pos)
                                        if not pos_details:
                                            continue

                                        if (pos_details['put_call'] == order_to_monitor['putCall'] and
                                            abs(pos_details['strike'] - order_to_monitor['strike']) < 0.001 and
                                            pos_details['expiry'] == order_to_monitor['expiry'] and
                                            pos_details['quantity'] != 0):
                                            position_verified = True
                                            break
                                    if position_verified:
                                        break

                            if position_verified:
                                print("Position verified. Proceeding with filled order workflow.")
                                return original_order_details, "FILLED"
                            else:
                                print("Original order was filled, but could not verify the new position. Restarting flow for safety.")
                                return None, "REPLACEMENT_NOT_FOUND"

                    # If we're here, the original order was not filled, and we can't find the replacement.
                    print("Could not find replacement order and original was not filled. Restarting flow.")
                    return None, "REPLACEMENT_NOT_FOUND"
            elif status in ['CANCELED', 'EXPIRED', 'REJECTED']:
                print(f"\nOrder not filled. Status: {status}")
                return order_details, status

            if poll_count % 4 == 0:
                try:
                    option_chain_response = client.get_option_chains(
                        symbol=order_to_monitor['symbol'],
                        strike=order_to_monitor['strike'],
                        fromDate=order_to_monitor['expiry'],
                        toDate=order_to_monitor['expiry'],
                        contractType='ALL'
                    )
                    if option_chain_response.get('success') and option_chain_response.get('data'):
                        oc_data = option_chain_response['data']
                        call_map = oc_data.get('callExpDateMap', {})
                        put_map = oc_data.get('putExpDateMap', {})
                        call_data, put_data = None, None
                        date_key_call = next((k for k in call_map if k.startswith(order_to_monitor['expiry'])), None)
                        if date_key_call:
                            strike_map_call = call_map.get(date_key_call, {})
                            for key_str, option_list in strike_map_call.items():
                                if abs(float(key_str) - order_to_monitor['strike']) < 0.001:
                                    call_data = option_list[0] if option_list else None
                                    break
                        date_key_put = next((k for k in put_map if k.startswith(order_to_monitor['expiry'])), None)
                        if date_key_put:
                            strike_map_put = put_map.get(date_key_put, {})
                            for key_str, option_list in strike_map_put.items():
                                if abs(float(key_str) - order_to_monitor['strike']) < 0.001:
                                    put_data = option_list[0] if option_list else None
                                    break
                        if call_data and put_data:
                            print(f"\n[{datetime.now().strftime('%H:%M:%S')}] "
                                  f"CALL: {format_price(call_data['bid'])}/{format_price(call_data['ask'])} | "
                                  f"PUT: {format_price(put_data['bid'])}/{format_price(put_data['ask'])} | "
                                  f"Monitoring: {order_summary}")
                        else:
                            print(f"\nCould not find option data for periodic update for strike {order_to_monitor['strike']}.")
                    else:
                        print(f"\nCould not fetch option chain for periodic update.")
                except Exception as e:
                    print(f"\nError during periodic update: {e}")
    finally:
        termios.tcsetattr(sys.stdin, termios.TCSADRAIN, old_settings)


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

def monitor_and_close_workflow(client, account_hash, order_to_monitor):
    """
    Monitors a given order until filled, then prompts to place a closing order.
    This function contains the main post-placement logic.
    """
    symbol = order_to_monitor['symbol']
    strike_price = order_to_monitor['strike']
    expiry_date = order_to_monitor['expiry']
    option_type_in = order_to_monitor['putCall'][0] # 'C' or 'P'
    quantity = order_to_monitor['quantity']
    side = order_to_monitor['instruction']

    filled_order, status = poll_order_status(client, account_hash, order_to_monitor)

    if status == "REPLACEMENT_NOT_FOUND":
        print("Aborting current workflow.")
        return

    if status == "FILLED":
        # If the order that filled was a closing order, the workflow is complete.
        if "TO_CLOSE" in side:
            print("\nPosition has been closed. Workflow complete.")
            return

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
            closing_call_data, closing_put_data = None, None

            date_key_call = next((k for k in closing_call_map if k.startswith(expiry_date)), None)
            if date_key_call:
                strike_map_call = closing_call_map.get(date_key_call, {})
                for key_str, option_list in strike_map_call.items():
                    if abs(float(key_str) - strike_price) < 0.001:
                        closing_call_data = option_list[0] if option_list else None
                        break

            date_key_put = next((k for k in closing_put_map if k.startswith(expiry_date)), None)
            if date_key_put:
                strike_map_put = closing_put_map.get(date_key_put, {})
                for key_str, option_list in strike_map_put.items():
                    if abs(float(key_str) - strike_price) < 0.001:
                        closing_put_data = option_list[0] if option_list else None
                        break

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
                closing_order_to_monitor = {
                    "orderId": closing_order_id,
                    "instruction": closing_side,
                    "quantity": quantity,
                    "symbol": symbol,
                    "putCall": "CALL" if option_type_in == 'C' else "PUT",
                    "strike": strike_price,
                    "expiry": expiry_date,
                    "price": closing_price
                }
                filled_closing_order, closing_status = poll_order_status(client, account_hash, closing_order_to_monitor)

                if closing_status == "REPLACEMENT_NOT_FOUND":
                    print("Aborting current workflow.")
                    return

                if closing_status == "FILLED":
                    entry_price = filled_order.get('orderActivityCollection', [{}])[0].get('executionLegs', [{}])[0].get('price')
                    exit_price = filled_closing_order.get('orderActivityCollection', [{}])[0].get('executionLegs', [{}])[0].get('price')

                    print("\n--- Trade Summary ---")
                    print(f"Action: {side}")
                    print(f"Entry Price: {format_price(entry_price)}")
                    print(f"Exit Action: {closing_side}")
                    print(f"Exit Price: {format_price(exit_price)}")
                    print("--------------------")

def place_order_workflow(client, account_hash, symbol, option_type_in, strike_price, expiry_date, action, price, positions_response, target_option_data):
    """Handles the entire workflow for placing and monitoring an order."""
    quantity = 1

    # Determine side
    current_quantity = 0
    if positions_response.get('success') and positions_response.get('data'):
        accounts = positions_response.get('data', {}).get('accounts', [])
        for acc in accounts:
            for pos in acc.get('positions', []):
                if pos.get('instrument', {}).get('symbol') == target_option_data.get('symbol'):
                    current_quantity = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
                    break
            if current_quantity != 0:
                break

    side = ""
    if action == 'B':
        side = "BUY_TO_CLOSE" if current_quantity < 0 else "BUY_TO_OPEN"
    else:  # 'S'
        side = "SELL_TO_CLOSE" if current_quantity > 0 else "SELL_TO_OPEN"

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
            # Construct the dictionary of details for the order to be monitored
            order_to_monitor = {
                "orderId": order_id,
                "instruction": side,
                "quantity": quantity,
                "symbol": symbol,
                "putCall": "CALL" if option_type_in == 'C' else "PUT",
                "strike": strike_price,
                "expiry": expiry_date,
                "price": price
            }
            monitor_and_close_workflow(client, account_hash, order_to_monitor)

def noni_1_main():
    """Main function for the interactive option client."""
    print("noni-1 : Schwab Interactive Option Client")
    print("Make sure the server is running before executing this script!")

    with SchwabClient() as client:
        account_hash = get_account_hash(client)
        if not account_hash:
            return

        print(f"Using account hash: {account_hash}")

        while True:
            try:

                symbol_input = input("\nEnter a stock symbol (or 'q' to quit): ").upper()
                if symbol_input in ['QUIT', 'Q']:
                    break
                symbol = symbol_input


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
                if strike_price_str:
                    try:
                        strike_price = float(strike_price_str)
                    except ValueError:
                        print("Invalid strike price entered. Using default.")
                        strike_price = suggested_strike
                else:
                    strike_price = suggested_strike

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
                                details = parse_option_position_details(pos)
                                if details:
                                    qty_str = f"+{int(details['quantity'])}" if details['quantity'] > 0 else str(int(details['quantity']))
                                    option_positions.append(f"{qty_str} {details['put_call']}; Strike: {details['strike']}; Expiry {details['expiry']}")
                                else:
                                    # Fallback for parsing failure
                                    qty = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
                                    option_positions.append(f"{int(qty)} of {pos.get('description', 'Unknown Option')}")

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

                    cancel_and_replace = input("Cancel existing order and place new one? (y/n): ").lower()
                    if cancel_and_replace in ['y', 'yes']:

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
                            new_order_id = replace_response.get('data', {}).get('new_order_id')
                            if new_order_id:
                                print(f"Order replaced successfully. Now monitoring new order: {new_order_id}")
                                # Construct the dictionary for the new order to be monitored
                                order_to_monitor = {
                                    "orderId": new_order_id,
                                    "instruction": side,
                                    "quantity": quantity,
                                    "symbol": symbol,
                                    "putCall": "CALL" if option_type_in == 'C' else "PUT",
                                    "strike": strike_price,
                                    "expiry": expiry_date,
                                    "price": price
                                }
                                # Start the monitoring and closing workflow
                                monitor_and_close_workflow(client, account_hash, order_to_monitor)
                                print("\nWorkflow complete. Returning to main menu.")
                            else:
                                print("WARNING: Replacement successful, but no new order ID was returned. Restarting flow.")
                        else:
                            print(f"Failed to replace order: {replace_response.get('error')}")

                        continue # Restart the main loop after the workflow is complete or has failed
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
    noni_1_main()
