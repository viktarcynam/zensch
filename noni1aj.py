import argparse
import sys
import time
import yaml
import random
from datetime import datetime
from client import SchwabClient
from trading_utils import get_nearest_strike, get_next_friday

def load_and_validate_rules(rules_file_path, cli_overrides):
    """
    Loads rules from YAML, applies CLI overrides, and validates the final rule set.
    """
    required_rules = [
        'spread', 'waitbidask', 'prefercp', 'preferBS', 'openingmaxtime', 'maxflowretry',
        'openretrytime', 'openpricefish', 'openpricemethod', 'closeretrytime',
        'closepricefish', 'closepricemethod', 'closingmaxtime', 'emergencyclosetime'
    ]
    try:
        with open(rules_file_path, 'r') as f:
            rules = yaml.safe_load(f)
        if not rules:
            print(f"Error: Rules file '{rules_file_path}' is empty. Exiting.")
            sys.exit(1)
        print(f"Successfully loaded rules from {rules_file_path}")
    except FileNotFoundError:
        print(f"Error: Rules file '{rules_file_path}' not found. Exiting.")
        sys.exit(1)
    except yaml.YAMLError as e:
        print(f"Error parsing YAML file '{rules_file_path}': {e}. Exiting.")
        sys.exit(1)

    # Apply CLI overrides
    if cli_overrides:
        rules.update(cli_overrides)
        print("Applied CLI overrides to rules.")

    missing_rules = [rule for rule in required_rules if rule not in rules]
    if missing_rules:
        print(f"Error: The following required rules are missing after applying overrides:")
        for rule in missing_rules:
            print(f"  - {rule}")
        sys.exit(1)

    # Perform validation
    if 'prefercp' in rules:
        rules['prefercp'] = rules['prefercp'].upper()
        if rules['prefercp'] not in ['C', 'P']:
            print(f"Error: Invalid 'prefercp' value '{rules['prefercp']}'. Must be 'C' or 'P'. Exiting.")
            sys.exit(1)
    if 'preferBS' in rules:
        rules['preferBS'] = rules['preferBS'].upper()
        if rules['preferBS'] not in ['B', 'S']:
            print(f"Error: Invalid 'preferBS' value '{rules['preferBS']}'. Must be 'B' or 'S'. Exiting.")
            sys.exit(1)
    return rules

def get_account_hash(client):
    """Get the first account hash."""
    accounts = client.get_linked_accounts()
    if accounts and accounts.get('success'):
        account_list = accounts.get('data', [])
        if account_list:
            return account_list[0].get('hashValue')
    print("Error: Could not retrieve account hash.")
    return None

def create_price_generator(initial_price, fish, method, side):
    """
    Creates a generator that yields new prices for replacement orders.
    """
    if side.startswith('BUY'):
        low = initial_price
        high = round(initial_price + fish, 2)
    else:  # SELL
        low = round(initial_price - fish, 2)
        high = initial_price
    if low < 0: low = 0.01
    if method == 'seq':
        prices = [round(low + i * 0.01, 2) for i in range(int(abs(high - low) * 100) + 1)]
        if not prices: prices = [low]
        current_index = 0
        while True:
            yield prices[current_index]
            current_index = (current_index + 1) % len(prices)
    else:  # random
        while True:
            yield round(random.uniform(low, high), 2)

def find_matching_order(client, account_hash, rules, option_type):
    """
    Finds a working or filled order that matches the instrument being traded.
    """
    print(f"[{rules.get('run_mode').upper()}] Searching for a matching order for {rules['symbol']} {option_type}...")
    statuses_to_check = ['WORKING', 'FILLED', 'PENDING_ACTIVATION', 'QUEUED']
    for status in statuses_to_check:
        orders_response = client.get_option_orders(account_id=account_hash, status=status, max_results=50)
        if orders_response.get('success'):
            for order in orders_response.get('data', []):
                for leg in order.get('orderLegCollection', []):
                    instrument = leg.get('instrument', {})
                    if (instrument.get('assetType') == 'OPTION' and
                        instrument.get('underlyingSymbol') == rules['symbol'] and
                        instrument.get('putCall') == option_type):

                        # More precise check using description parsing if needed, but this is often enough
                        from trading_utils import parse_instrument_description
                        desc_details = parse_instrument_description(instrument.get('description'))
                        if desc_details and abs(desc_details['strike'] - rules['strike']) < 0.001 and desc_details['expiry'] == rules['expiry']:
                            print(f"[{rules.get('run_mode').upper()}] Found matching order {order.get('orderId')} with status {order.get('status')}")
                            return order
    print(f"[{rules.get('run_mode').upper()}] No matching order found yet.")
    return None

def handle_opening_state(client, account_hash, rules, selected_option):
    """
    Manages the logic for placing, monitoring, and replacing the opening order.
    """
    side = "BUY_TO_OPEN" if rules['preferBS'] == 'B' else "SELL_TO_OPEN"
    if side == "BUY_TO_OPEN":
        initial_price = round(selected_option['bid'] + 0.01, 2)
    else:
        initial_price = round(selected_option['ask'] - 0.01, 2)
    if initial_price <= 0:
        print(f"[OPENING] Error: Calculated initial price is {initial_price}. Must be positive. Aborting.")
        return {'status': 'FAILED'}

    run_mode = rules.get('run_mode')

    # --- External Run Mode ---
    if run_mode == 'external_run':
        print_bold(f"\n[EXTERNAL] Please place the following order manually:")
        print_bold(f"  ACTION: {side} 1 {selected_option['type']} {rules['symbol']} @ STRIKE {rules['strike']} EXP {rules['expiry']}")
        print_bold(f"  PRICE:  LIMIT @ {initial_price:.2f}")

        opening_start_time = time.time()
        last_suggestion_time = time.time()
        price_generator = create_price_generator(initial_price, rules['openpricefish'], rules['openpricemethod'], side)

        while time.time() - opening_start_time < rules['openingmaxtime']:
            external_order = find_matching_order(client, account_hash, rules, selected_option['type'])
            if external_order:
                if external_order.get('status') == 'FILLED':
                    print("[EXTERNAL] Detected externally placed order has been FILLED.")
                    return {'status': 'FILLED', 'order': external_order}
                else: # It's working, so monitor it
                    print(f"[EXTERNAL] Detected working order {external_order.get('orderId')}. Monitoring for fill.")
                    # Let this inner loop run for the extended retry time
                    if time.time() - last_suggestion_time > (rules['openretrytime'] * 10):
                        new_price = next(price_generator)
                        print_bold(f"\n[EXTERNAL] Order has not filled. It is recommended to replace it with a new price: {new_price:.2f}")
                        last_suggestion_time = time.time() # Reset timer after suggestion

            print(f"  [EXTERNAL] Waiting for user to place/fill order...", end='\r')
            time.sleep(10) # Poll less frequently in external mode

        print("\n[EXTERNAL] Opening state timed out.")
        return {'status': 'TIMEOUT'}

    # --- Live and Dry Run Modes ---
    action_msg = f"[OPENING] Placing initial order: {side} 1 {selected_option['type']} @ {initial_price:.2f}"
    print(action_msg)
    if run_mode == 'live':
        order_response = client.place_option_order(
            account_id=account_hash, symbol=rules['symbol'], option_type=selected_option['type'],
            expiration_date=rules['expiry'], strike_price=rules['strike'], quantity=1,
            side=side, order_type="LIMIT", price=initial_price)
        if not order_response.get('success'):
            print(f"[OPENING] Error placing order: {order_response.get('error')}")
            return {'status': 'FAILED'}
        current_order_id = order_response.get('data', {}).get('order_id')
        print(f"[OPENING] Initial order placed. Order ID: {current_order_id}")
    else: # dry_run
        current_order_id = f"dry_run-open-{int(time.time())}"
        print(f"[DRY RUN] [OPENING] Simulated Order ID: {current_order_id}")
        mock_fill_time = time.time() + random.uniform(5, rules['openingmaxtime'] * 0.8)

    opening_start_time = time.time()
    last_replacement_time = time.time()
    price_generator = create_price_generator(initial_price, rules['openpricefish'], rules['openpricemethod'], side)
    current_price = initial_price
    while time.time() - opening_start_time < rules['openingmaxtime']:
        if run_mode == 'live':
            details_response = client.get_option_order_details(account_id=account_hash, order_id=current_order_id)
            if details_response.get('success'):
                status = details_response.get('data', {}).get('status')
                if status == 'FILLED':
                    print(f"\n[OPENING] SUCCESS: Order {current_order_id} filled!")
                    return {'status': 'FILLED', 'order': details_response.get('data')}
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    print(f"\n[OPENING] Order {current_order_id} is dead ({status}). Aborting.")
                    return {'status': 'FAILED'}

        if run_mode == 'dry_run' and time.time() > mock_fill_time:
            print(f"\n[DRY RUN] [OPENING] Simulating a FILLED order.")
            fake_filled_order = {
                'orderLegCollection': [{'instruction': side, 'quantity': 1, 'instrument': {'putCall': selected_option['type']}}],
                'orderActivityCollection': [{'executionLegs': [{'price': current_price, 'quantity': 1}]}]
            }
            return {'status': 'FILLED', 'order': fake_filled_order}

        if time.time() - last_replacement_time > rules['openretrytime']:
            new_price = next(price_generator)
            if abs(new_price - current_price) > 0.001:
                current_price = new_price
                replace_msg = f"[OPENING] Replacing order with new price: {current_price:.2f}"
                print(f"\n{replace_msg}")
                if run_mode == 'live':
                    replace_response = client.replace_option_order(
                        account_id=account_hash, order_id=current_order_id, symbol=rules['symbol'],
                        option_type=selected_option['type'], expiration_date=rules['expiry'],
                        strike_price=rules['strike'], quantity=1, side=side, order_type="LIMIT", price=current_price)
                    if replace_response.get('success'):
                        new_order_id = replace_response.get('data', {}).get('new_order_id')
                        print(f"[OPENING] Replacement successful. New Order ID: {new_order_id}")
                        current_order_id = new_order_id
                    else:
                        print(f"[OPENING] Error replacing order: {replace_response.get('error')}")
                else:
                    current_order_id = f"{run_mode}-replace-{int(time.time())}"
                    print(f"[{run_mode.upper()}] [OPENING] Simulated New Order ID: {current_order_id}")
                last_replacement_time = time.time()

        status_msg = f"[OPENING] Monitoring order {current_order_id} at price {current_price:.2f}..."
        print(f"  {status_msg}", end='\r')
        time.sleep(5)

    print(f"\n[OPENING] Timed out after {rules['openingmaxtime']}s. Cancelling order.")
    if run_mode == 'live':
        client.cancel_option_order(account_id=account_hash, order_id=current_order_id)
    else:
        print(f"[{run_mode.upper()}] [OPENING] Would have cancelled order {current_order_id}")
    return {'status': 'TIMEOUT'}

def handle_closing_state(client, account_hash, rules, filled_opening_order):
    """
    Manages the logic for placing and monitoring the closing order.
    """
    opening_leg = filled_opening_order['orderLegCollection'][0]
    side = "SELL_TO_CLOSE" if opening_leg['instruction'] == "BUY_TO_OPEN" else "BUY_TO_CLOSE"
    quantity = opening_leg['quantity']
    option_type = opening_leg['instrument']['putCall']

    print(f"\n[CLOSING] Fetching latest quote to determine initial closing price...")
    chain_response = client.get_option_chains(symbol=rules['symbol'], strike=rules['strike'], fromDate=rules['expiry'], toDate=rules['expiry'], contractType=option_type)
    if not chain_response.get('success') or not chain_response.get('data'):
        print("[CLOSING] Error: Could not fetch latest quote for closing order. Aborting.")
        return {'status': 'FAILED'}
    try:
        exp_map_key = 'callExpDateMap' if option_type == 'CALL' else 'putExpDateMap'
        date_key = next(iter(chain_response['data'][exp_map_key]))
        option_data = chain_response['data'][exp_map_key][date_key][str(float(rules['strike']))][0]
        latest_bid = option_data.get('bid', 0.0)
        latest_ask = option_data.get('ask', 0.0)
    except (KeyError, IndexError, StopIteration):
        print("[CLOSING] Error: Could not parse latest quote from option chain. Aborting.")
        return {'status': 'FAILED'}

    if side == "SELL_TO_CLOSE":
        initial_price = round(latest_ask - 0.01, 2)
    else:
        initial_price = round(latest_bid + 0.01, 2)
    if initial_price <= 0:
        print(f"[CLOSING] Error: Calculated initial closing price is {initial_price}. Must be positive. Aborting.")
        return {'status': 'FAILED'}

    action_msg = f"[CLOSING] Placing initial order: {side} {quantity} {option_type} @ {initial_price:.2f}"
    print(action_msg)

    run_mode = rules.get('run_mode')

    # --- External Run Mode ---
    if run_mode == 'external_run':
        print_bold(f"\n[EXTERNAL] Please place the following closing order manually:")
        print_bold(f"  ACTION: {side} {quantity} {option_type} {rules['symbol']} @ STRIKE {rules['strike']} EXP {rules['expiry']}")
        print_bold(f"  PRICE:  LIMIT @ {initial_price:.2f}")

        closing_start_time = time.time()
        last_suggestion_time = time.time()
        price_generator = create_price_generator(initial_price, rules['closepricefish'], rules['closepricemethod'], side)

        while time.time() - closing_start_time < rules['closingmaxtime']:
            # In external mode, we check if the position is gone
            position_response = client.get_positions_by_symbol(symbol=rules['symbol'], account_hash=account_hash)
            position_closed = True
            if position_response.get('success') and position_response.get('data'):
                accounts = position_response.get('data', {}).get('accounts', [])
                for acc in accounts:
                    for pos in acc.get('positions', []):
                        # Find the specific option position
                        from trading_utils import parse_option_position_details
                        pos_details = parse_option_position_details(pos)
                        if (pos_details and pos_details['put_call'] == option_type and
                            abs(pos_details['strike'] - rules['strike']) < 0.001 and
                            pos_details['expiry'] == rules['expiry'] and pos_details['quantity'] != 0):
                            position_closed = False
                            break
                    if not position_closed:
                        break

            if position_closed:
                print("\n[EXTERNAL] Position has been closed successfully.")
                # We don't have the real closing order, so we can't do a P/L summary
                return {'status': 'CLOSED', 'order': None}

            # If position not closed, check for a working order to suggest replacements for
            working_order = find_matching_order(client, account_hash, rules, option_type)
            if working_order and working_order.get('status') != 'FILLED':
                if time.time() - last_suggestion_time > (rules['closeretrytime'] * 10):
                    new_price = next(price_generator)
                    print_bold(f"\n[EXTERNAL] Closing order has not filled. It is recommended to replace it with a new price: {new_price:.2f}")
                    last_suggestion_time = time.time()

            print(f"  [EXTERNAL] Waiting for user to close position...", end='\r')
            time.sleep(10)

        print("\n[EXTERNAL] Closing state timed out.")
        return {'status': 'TIMEOUT'}

    # --- Live and Dry Run Modes ---
    if run_mode == 'live':
        order_response = client.place_option_order(
            account_id=account_hash, symbol=rules['symbol'], option_type=option_type,
            expiration_date=rules['expiry'], strike_price=rules['strike'], quantity=quantity,
            side=side, order_type="LIMIT", price=initial_price)
        if not order_response.get('success'):
            print(f"[CLOSING] Error placing closing order: {order_response.get('error')}")
            return {'status': 'FAILED'}
        current_order_id = order_response.get('data', {}).get('order_id')
        print(f"[CLOSING] Initial order placed. Order ID: {current_order_id}")
    else: # dry_run
        current_order_id = f"dry_run-close-{int(time.time())}"
        print(f"[DRY RUN] [CLOSING] Simulated Order ID: {current_order_id}")
        mock_outcome = random.choice(['FILLED', 'TIMEOUT'])
        print(f"[DRY RUN] [CLOSING] This order's simulated outcome will be: {mock_outcome}")
        if mock_outcome == 'FILLED':
            mock_fill_time = time.time() + random.uniform(5, rules['closingmaxtime'] * 0.8)

    closing_start_time = time.time()
    last_replacement_time = time.time()
    price_generator = create_price_generator(initial_price, rules['closepricefish'], rules['closepricemethod'], side)
    current_price = initial_price
    while time.time() - closing_start_time < rules['closingmaxtime']:
        if run_mode == 'live':
            details_response = client.get_option_order_details(account_id=account_hash, order_id=current_order_id)
            if details_response.get('success'):
                status = details_response.get('data', {}).get('status')
                if status == 'FILLED':
                    print(f"\n[CLOSING] SUCCESS: Order {current_order_id} filled!")
                    return {'status': 'CLOSED', 'order': details_response.get('data')}
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    print(f"\n[CLOSING] Order {current_order_id} is dead ({status}). Aborting.")
                    return {'status': 'FAILED'}

        if run_mode == 'dry_run' and mock_outcome == 'FILLED' and time.time() > mock_fill_time:
            print(f"\n[DRY RUN] [CLOSING] Simulating a FILLED order.")
            fake_filled_order = {
                'orderLegCollection': [{'instruction': side, 'quantity': quantity, 'instrument': {'putCall': option_type}}],
                'orderActivityCollection': [{'executionLegs': [{'price': current_price, 'quantity': quantity}]}]
            }
            return {'status': 'CLOSED', 'order': fake_filled_order}

        if time.time() - last_replacement_time > rules['closeretrytime']:
            new_price = next(price_generator)
            if abs(new_price - current_price) > 0.001:
                current_price = new_price
                replace_msg = f"[CLOSING] Replacing order with new price: {current_price:.2f}"
                print(f"\n{replace_msg}")
                if run_mode == 'live':
                    replace_response = client.replace_option_order(
                        account_id=account_hash, order_id=current_order_id, symbol=rules['symbol'],
                        option_type=option_type, expiration_date=rules['expiry'], strike_price=rules['strike'],
                        quantity=quantity, side=side, order_type="LIMIT", price=current_price)
                    if replace_response.get('success'):
                        new_order_id = replace_response.get('data', {}).get('new_order_id')
                        print(f"[CLOSING] Replacement successful. New Order ID: {new_order_id}")
                        current_order_id = new_order_id
                    else:
                        print(f"[CLOSING] Error replacing closing order: {replace_response.get('error')}")
                else:
                    current_order_id = f"{run_mode}-close-replace-{int(time.time())}"
                    print(f"[{run_mode.upper()}] [CLOSING] Simulated New Order ID: {current_order_id}")
                last_replacement_time = time.time()

        status_msg = f"[CLOSING] Monitoring order {current_order_id} at price {current_price:.2f}..."
        print(f"  {status_msg}", end='\r')
        time.sleep(5)

    print(f"\n[CLOSING] Timed out after {rules['closingmaxtime']}s. Cancelling order.")
    if run_mode == 'live':
        client.cancel_option_order(account_id=account_hash, order_id=current_order_id)
    else:
        print(f"[{run_mode.upper()}] [CLOSING] Would have cancelled order {current_order_id}")
    return {'status': 'TIMEOUT'}

def print_bold(text):
    """Prints text in bold using ANSI escape codes."""
    print(f"\033[1m{text}\033[0m")

def handle_emergency_close(client, account_hash, rules, filled_opening_order):
    """
    Final attempt to close the position at the break-even price.
    """
    try:
        opening_leg = filled_opening_order['orderLegCollection'][0]
        opening_activity = filled_opening_order['orderActivityCollection'][0]['executionLegs'][0]
        side = "SELL_TO_CLOSE" if opening_leg['instruction'] == "BUY_TO_OPEN" else "BUY_TO_CLOSE"
        quantity = opening_leg['quantity']
        option_type = opening_leg['instrument']['putCall']
        break_even_price = opening_activity['price']
    except (KeyError, IndexError):
        print_bold("\n[EMERGENCY] CRITICAL ERROR: Could not parse filled opening order to determine parameters.")
        return {'status': 'UNCLOSED'}

    action_msg = f"[EMERGENCY] Placing order: {side} {quantity} {option_type} @ break-even price {break_even_price:.2f}"
    print(action_msg)

    run_mode = rules.get('run_mode')

    # --- External Run Mode ---
    if run_mode == 'external_run':
        print_bold(f"\n[EXTERNAL] Please place the following emergency order manually:")
        print_bold(f"  ACTION: {side} {quantity} {option_type} {rules['symbol']} @ STRIKE {rules['strike']} EXP {rules['expiry']}")
        print_bold(f"  PRICE:  LIMIT @ {break_even_price:.2f}")

        emergency_start_time = time.time()
        while time.time() - emergency_start_time < rules['emergencyclosetime']:
            position_response = client.get_positions_by_symbol(symbol=rules['symbol'], account_hash=account_hash)
            position_closed = True
            if position_response.get('success') and position_response.get('data'):
                accounts = position_response.get('data', {}).get('accounts', [])
                for acc in accounts:
                    for pos in acc.get('positions', []):
                        from trading_utils import parse_option_position_details
                        pos_details = parse_option_position_details(pos)
                        if (pos_details and pos_details['put_call'] == option_type and
                            abs(pos_details['strike'] - rules['strike']) < 0.001 and
                            pos_details['expiry'] == rules['expiry'] and pos_details['quantity'] != 0):
                            position_closed = False
                            break
                    if not position_closed:
                        break
            if position_closed:
                print("\n[EXTERNAL] Position has been closed successfully during emergency.")
                return {'status': 'CLOSED_EMERGENCY', 'order': None}

            print(f"  [EXTERNAL] Waiting for user to close position...", end='\r')
            time.sleep(10)

        # If loop finishes, timeout occurred
        return {'status': 'UNCLOSED'} # The final warning will be printed by the caller

    # --- Live and Dry Run Modes ---
    if run_mode == 'live':
        order_response = client.place_option_order(
            account_id=account_hash, symbol=rules['symbol'], option_type=option_type,
            expiration_date=rules['expiry'], strike_price=rules['strike'], quantity=quantity,
            side=side, order_type="LIMIT", price=break_even_price)
        if not order_response.get('success'):
            print_bold(f"[EMERGENCY] CRITICAL ERROR: Failed to place emergency close order: {order_response.get('error')}")
            return {'status': 'UNCLOSED'}
        current_order_id = order_response.get('data', {}).get('order_id')
        print(f"[EMERGENCY] Order placed. Order ID: {current_order_id}")
    else: # dry_run
        current_order_id = f"dry_run-emergency-{int(time.time())}"
        print(f"[DRY RUN] [EMERGENCY] Simulated Order ID: {current_order_id}")
        mock_outcome = random.choice(['CLOSED_EMERGENCY', 'UNCLOSED'])
        print(f"[DRY RUN] [EMERGENCY] This order's simulated outcome will be: {mock_outcome}")
        if mock_outcome == 'CLOSED_EMERGENCY':
            mock_fill_time = time.time() + random.uniform(2, rules['emergencyclosetime'] * 0.8)

    emergency_start_time = time.time()
    while time.time() - emergency_start_time < rules['emergencyclosetime']:
        if run_mode == 'live':
            details_response = client.get_option_order_details(account_id=account_hash, order_id=current_order_id)
            if details_response.get('success') and details_response.get('data', {}).get('status') == 'FILLED':
                print(f"\n[EMERGENCY] SUCCESS: Order {current_order_id} filled!")
                return {'status': 'CLOSED_EMERGENCY', 'order': details_response.get('data')}

        if run_mode == 'dry_run' and mock_outcome == 'CLOSED_EMERGENCY' and time.time() > mock_fill_time:
            print(f"\n[DRY RUN] [EMERGENCY] Simulating a FILLED order.")
            fake_filled_order = {
                'orderLegCollection': [{'instruction': side, 'quantity': quantity, 'instrument': {'putCall': option_type}}],
                'orderActivityCollection': [{'executionLegs': [{'price': break_even_price, 'quantity': quantity}]}]
            }
            return {'status': 'CLOSED_EMERGENCY', 'order': fake_filled_order}

        status_msg = f"[EMERGENCY] Monitoring order {current_order_id}..."
        print(f"  {status_msg}", end='\r')
        time.sleep(5)

    print("\n" + "="*60)
    print_bold("!!! [EMERGENCY] CRITICAL FAILURE: UNABLE TO CLOSE POSITION AUTOMATICALLY !!!")
    print_bold("MANUAL INTERVENTION REQUIRED IMMEDIATELY.")
    print("="*60)
    print_bold("Position Details:")
    print_bold(f"  Symbol: {rules['symbol'].upper()}")
    print_bold(f"  Type:   {quantity} {option_type} @ Strike {rules['strike']} Expiring {rules['expiry']}")
    print_bold(f"  Side:   {'LONG' if side == 'SELL_TO_CLOSE' else 'SHORT'}")
    print("="*60)
    return {'status': 'UNCLOSED'}

def print_trade_summary(open_order, close_order):
    """Prints a summary of the completed trade."""
    try:
        open_leg = open_order['orderActivityCollection'][0]['executionLegs'][0]
        close_leg = close_order['orderActivityCollection'][0]['executionLegs'][0]
        entry_price = open_leg['price']
        exit_price = close_leg['price']
        quantity = open_leg['quantity']
        side = open_order['orderLegCollection'][0]['instruction']
        p_l_per_contract = exit_price - entry_price if side == 'BUY_TO_OPEN' else entry_price - exit_price
        total_p_l = p_l_per_contract * quantity * 100
        print("\n" + "="*30)
        print_bold("Trade Summary")
        print(f"  Entry Price: {entry_price:.2f}")
        print(f"  Exit Price:  {exit_price:.2f}")
        print(f"  P/L:         ${total_p_l:.2f}")
        print("="*30)
    except (KeyError, IndexError, TypeError) as e:
        print("\nCould not generate trade summary due to unexpected order format.")
        print(f"Error: {e}")

def run_bot(rules):
    """
    The main bot logic, containing the full state machine.
    """
    with SchwabClient() as client:
        account_hash = get_account_hash(client)
        if not account_hash:
            return

        # Determine strike and expiry using the new precedence: CLI > Rules File > Dynamic
        if rules.get('strike') is None or rules.get('expiry') is None:
            print("[SETUP] Strike or expiry not found in args or rules, fetching defaults...")
            quotes_response = client.get_quotes(symbols=[rules['symbol']])
            if not quotes_response.get('success') or not quotes_response.get('data'):
                print(f"[SETUP] Error: Could not retrieve quote for {rules['symbol']} to determine defaults. Exiting.")
                return
            try:
                quote_string = quotes_response['data'][0]
                last_price = float(quote_string.split()[1])
                print(f"[SETUP] Current price for {rules['symbol']}: {last_price:.2f}")
            except (ValueError, IndexError):
                print(f"[SETUP] Error: Could not parse last price for {rules['symbol']}. Exiting.")
                return

            if rules.get('strike') is None:
                rules['strike'] = get_nearest_strike(last_price)
                print(f"[SETUP] Using dynamically calculated strike: {rules['strike']:.2f}")
            if rules.get('expiry') is None:
                rules['expiry'] = get_next_friday()
                print(f"[SETUP] Using dynamically calculated expiry: {rules['expiry']}")

        print("\nFinal Configuration:")
        print(f"  Strike: {rules['strike']:.2f}")
        print(f"  Expiry: {rules['expiry']}")
        print("-" * 20)

        retries_left = rules.get('maxflowretry', 1)
        while retries_left > 0:
            print(f"\n--- Starting Flow Attempt ({rules.get('maxflowretry', 1) - retries_left + 1}/{rules.get('maxflowretry', 1)}) ---")
            # --- SEARCHING STATE ---
            print("[SEARCHING] Entering state")
            search_start_time = time.time()
            wait_time = rules['waitbidask']
            selected_option = None
            while time.time() - search_start_time < wait_time:
                print(f"[SEARCHING] Fetching option chain...")
                if rules.get('run_mode') != 'live': print(f"[{rules.get('run_mode').upper()}] [SEARCHING] Simulating fetch.")
                option_chain_response = client.get_option_chains(symbol=rules['symbol'], strike=rules['strike'], fromDate=rules['expiry'], toDate=rules['expiry'], contractType='ALL')
                if not option_chain_response.get('success') or not option_chain_response.get('data'):
                    print(f"[SEARCHING] Error: Could not retrieve option chain: {option_chain_response.get('error')}")
                    time.sleep(5)
                    continue
                option_chain_data = option_chain_response.get('data', {})
                call_map = option_chain_data.get('callExpDateMap', {})
                put_map = option_chain_data.get('putExpDateMap', {})
                call_data, put_data = None, None
                date_key_call = next((k for k in call_map if k.startswith(rules['expiry'])), None)
                if date_key_call:
                    call_data = call_map.get(date_key_call, {}).get(str(float(rules['strike'])), [None])[0]
                date_key_put = next((k for k in put_map if k.startswith(rules['expiry'])), None)
                if date_key_put:
                    put_data = put_map.get(date_key_put, {}).get(str(float(rules['strike'])), [None])[0]
                if not call_data or not put_data:
                    print("[SEARCHING] Could not find option data for the specified strike and date.")
                    time.sleep(5)
                    continue
                call_bid = call_data.get('bid', 0.0); call_ask = call_data.get('ask', 0.0)
                put_bid = put_data.get('bid', 0.0); put_ask = put_data.get('ask', 0.0)
                call_spread = call_ask - call_bid; put_spread = put_ask - put_bid
                print(f"[SEARCHING] CALL: Bid={call_bid:.2f}, Ask={call_ask:.2f}, Spread={call_spread:.2f}")
                print(f"[SEARCHING] PUT:  Bid={put_bid:.2f}, Ask={put_ask:.2f}, Spread={put_spread:.2f}")
                min_spread = rules['spread']
                call_valid = call_spread >= min_spread and call_bid > 0 and call_ask > 0
                put_valid = put_spread >= min_spread and put_bid > 0 and put_ask > 0
                if not (call_valid or put_valid):
                    print(f"[SEARCHING] Spread for both is below the minimum of {min_spread:.2f} or prices are zero. Waiting...")
                    time.sleep(5)
                    continue
                if call_valid and put_valid:
                    print(f"[SEARCHING] Both CALL and PUT are valid. Preferring '{rules['prefercp']}'.")
                    selected_option = {'type': 'CALL', 'bid': call_bid, 'ask': call_ask} if rules['prefercp'] == 'C' else {'type': 'PUT', 'bid': put_bid, 'ask': put_ask}
                elif call_valid:
                    print("[SEARCHING] CALL option is valid.")
                    selected_option = {'type': 'CALL', 'bid': call_bid, 'ask': call_ask}
                else:
                    print("[SEARCHING] PUT option is valid.")
                    selected_option = {'type': 'PUT', 'bid': put_bid, 'ask': put_ask}
                break

            if selected_option:
                print(f"\n[STATE_TRANSITION] Found suitable option: {selected_option['type']}. Entering Opening State.")
                opening_result = handle_opening_state(client, account_hash, rules, selected_option)
                if opening_result.get('status') == 'FILLED':
                    print("\n[STATE_TRANSITION] Opening Order Filled. Entering Closing State.")
                    closing_result = handle_closing_state(client, account_hash, rules, opening_result.get('order'))
                    if closing_result.get('status') == 'CLOSED':
                        print("\n[COMPLETE] TRADE COMPLETE: Closing order filled successfully!")
                        print_trade_summary(opening_result.get('order'), closing_result.get('order'))
                        break
                    elif closing_result.get('status') == 'TIMEOUT':
                        print("\n[STATE_TRANSITION] Closing state timed out. Entering Emergency Close.")
                        emergency_result = handle_emergency_close(client, account_hash, rules, opening_result.get('order'))
                        if emergency_result.get('status') == 'CLOSED_EMERGENCY':
                            print("\n[COMPLETE] TRADE COMPLETE: Position closed at break-even during emergency period.")
                            print_trade_summary(opening_result.get('order'), emergency_result.get('order'))
                        else:
                            print("\n[INCOMPLETE] BOT EXITING WITH OPEN POSITION.")
                        break
                    else:
                        print("\n[INCOMPLETE] Closing state failed unexpectedly. Manual intervention may be required.")
                        break
                else:
                    print(f"\n[INCOMPLETE] Opening state failed: {opening_result.get('status')}.")
                    retries_left -= 1
                    if retries_left > 0:
                        print(f"Retries left: {retries_left}. Restarting flow...")
                    else:
                        print("Max retries exceeded. Exiting.")
                        break
            else:
                print(f"\n[INCOMPLETE] Search timed out after {wait_time} seconds. No suitable trade found.")
                retries_left -= 1
                if retries_left > 0:
                    print(f"Retries left: {retries_left}. Restarting flow...")
                else:
                    print("Max retries exceeded. Exiting.")
                    break

    print(f"\n[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Bot finished.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="noni1aj - Automated Options Trading Bot")
    parser.add_argument("--symbol", required=True, help="The stock symbol to trade.")
    parser.add_argument("--rules-file", help="Path to the YAML rules file. Defaults to <symbol>-rules.yml.")
    parser.add_argument("--strike", type=float, help="The strike price. Overrides rules file.")
    parser.add_argument("--expiry", help="The expiry date (YYYY-MM-DD). Overrides rules file.")

    # Run modes
    run_mode_group = parser.add_mutually_exclusive_group()
    run_mode_group.add_argument("--dry-run", action="store_true", help="Simulate trading with random outcomes.")
    run_mode_group.add_argument("--external-run", action="store_true", help="Suggest trades for manual execution.")

    # Rule overrides
    parser.add_argument("--spread", type=float, help="Override rule: minimum bid-ask spread.")
    parser.add_argument("--waitbidask", type=int, help="Override rule: seconds to wait for a valid spread.")
    parser.add_argument("--prefer-cp", choices=['C', 'P'], help="Override rule: prefer Call or Put.")
    parser.add_argument("--prefer-bs", choices=['B', 'S'], help="Override rule: prefer Buy or Sell for opening.")
    parser.add_argument("--openingmaxtime", type=int, help="Override rule: max seconds to fill opening order.")
    parser.add_argument("--maxflowretry", type=int, help="Override rule: max number of times to restart flow.")
    parser.add_argument("--openretrytime", type=int, help="Override rule: seconds before replacing open order.")
    parser.add_argument("--openpricefish", type=float, help="Override rule: amount to adjust open price by.")
    parser.add_argument("--openpricemethod", choices=['seq', 'random'], help="Override rule: method for open price adjustment.")
    parser.add_argument("--closeretrytime", type=int, help="Override rule: seconds before replacing close order.")
    parser.add_argument("--closepricefish", type=float, help="Override rule: amount to adjust close price by.")
    parser.add_argument("--closepricemethod", choices=['seq', 'random'], help="Override rule: method for close price adjustment.")
    parser.add_argument("--closingmaxtime", type=int, help="Override rule: max seconds to fill closing order.")
    parser.add_argument("--emergencyclosetime", type=int, help="Override rule: max seconds for emergency close.")

    args = parser.parse_args()

    print("=============================================")
    print("         noni1aj - Trading Bot         ")
    print("=============================================")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Starting bot for symbol: {args.symbol}")

    rules_file = args.rules_file or f"{args.symbol.lower()}-rules.yml"

    # Collect CLI overrides into a dictionary, excluding None values
    cli_overrides = {k: v for k, v in vars(args).items() if v is not None and k not in ['symbol', 'rules_file', 'dry_run', 'external_run', 'strike', 'expiry']}

    rules = load_and_validate_rules(rules_file, cli_overrides)

    # Set run mode
    if args.dry_run:
        rules['run_mode'] = 'dry_run'
        print("\n*** DRY RUN MODE ENABLED - Simulating trades with random outcomes. ***\n")
    elif args.external_run:
        rules['run_mode'] = 'external_run'
        print("\n*** EXTERNAL RUN MODE ENABLED - Bot will suggest trades for manual execution. ***\n")
    else:
        rules['run_mode'] = 'live'

    # Pass essential args into the rules dict for easier access
    rules['symbol'] = args.symbol
    rules['strike'] = args.strike
    rules['expiry'] = args.expiry

    # Initialize the bot's main logic
    run_bot(rules)
