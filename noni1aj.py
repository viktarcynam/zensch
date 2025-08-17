import argparse
import sys
import time
import yaml
import random
from datetime import datetime
from client import SchwabClient
from trading_utils import get_nearest_strike, get_next_friday

def load_and_validate_rules(rules_file_path):
    """
    Loads and validates rules from a YAML file. Exits if file or any rule is missing.
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

    missing_rules = [rule for rule in required_rules if rule not in rules]
    if missing_rules:
        print(f"Error: The following required rules are missing from '{rules_file_path}':")
        for rule in missing_rules:
            print(f"  - {rule}")
        sys.exit(1)
    if 'dryrun' not in rules:
        rules['dryrun'] = False
    rules['prefercp'] = rules['prefercp'].upper()
    rules['preferBS'] = rules['preferBS'].upper()
    if rules['prefercp'] not in ['C', 'P']:
        print(f"Error: Invalid 'prefercp' value '{rules['prefercp']}'. Must be 'C' or 'P'. Exiting.")
        sys.exit(1)
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

def handle_opening_state(client, account_hash, args, rules, selected_option):
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

    action_msg = f"[OPENING] Placing initial order: {side} 1 {selected_option['type']} @ {initial_price:.2f}"
    print(action_msg)
    if not rules['dryrun']:
        order_response = client.place_option_order(
            account_id=account_hash, symbol=args.symbol, option_type=selected_option['type'],
            expiration_date=args.expiry, strike_price=args.strike, quantity=1,
            side=side, order_type="LIMIT", price=initial_price)
        if not order_response.get('success'):
            print(f"[OPENING] Error placing order: {order_response.get('error')}")
            return {'status': 'FAILED'}
        current_order_id = order_response.get('data', {}).get('order_id')
        print(f"[OPENING] Initial order placed. Order ID: {current_order_id}")
    else:
        current_order_id = f"dryrun-{int(time.time())}"
        print(f"[DRY RUN] [OPENING] Simulated Order ID: {current_order_id}")

    opening_start_time = time.time()
    last_replacement_time = time.time()
    price_generator = create_price_generator(initial_price, rules['openpricefish'], rules['openpricemethod'], side)
    current_price = initial_price
    while time.time() - opening_start_time < rules['openingmaxtime']:
        if not rules['dryrun']:
            details_response = client.get_option_order_details(account_id=account_hash, order_id=current_order_id)
            if details_response.get('success'):
                status = details_response.get('data', {}).get('status')
                if status == 'FILLED':
                    print(f"\n[OPENING] SUCCESS: Order {current_order_id} filled!")
                    return {'status': 'FILLED', 'order': details_response.get('data')}
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    print(f"\n[OPENING] Order {current_order_id} is dead ({status}). Aborting.")
                    return {'status': 'FAILED'}
        if time.time() - last_replacement_time > rules['openretrytime']:
            new_price = next(price_generator)
            if abs(new_price - current_price) > 0.001:
                current_price = new_price
                replace_msg = f"[OPENING] Replacing order with new price: {current_price:.2f}"
                print(f"\n{replace_msg}")
                if not rules['dryrun']:
                    replace_response = client.replace_option_order(
                        account_id=account_hash, order_id=current_order_id, symbol=args.symbol,
                        option_type=selected_option['type'], expiration_date=args.expiry,
                        strike_price=args.strike, quantity=1, side=side, order_type="LIMIT", price=current_price)
                    if replace_response.get('success'):
                        new_order_id = replace_response.get('data', {}).get('new_order_id')
                        print(f"[OPENING] Replacement successful. New Order ID: {new_order_id}")
                        current_order_id = new_order_id
                    else:
                        print(f"[OPENING] Error replacing order: {replace_response.get('error')}")
                else:
                    current_order_id = f"dryrun-replace-{int(time.time())}"
                    print(f"[DRY RUN] [OPENING] Simulated New Order ID: {current_order_id}")
                last_replacement_time = time.time()

        status_msg = f"[OPENING] Monitoring order {current_order_id} at price {current_price:.2f}..."
        print(f"  {status_msg}", end='\r')
        time.sleep(5)

    print(f"\n[OPENING] Timed out after {rules['openingmaxtime']}s. Cancelling order.")
    if not rules['dryrun']:
        client.cancel_option_order(account_id=account_hash, order_id=current_order_id)
    else:
        print(f"[DRY RUN] [OPENING] Would have cancelled order {current_order_id}")
    return {'status': 'TIMEOUT'}

def handle_closing_state(client, account_hash, args, rules, filled_opening_order):
    """
    Manages the logic for placing and monitoring the closing order.
    """
    opening_leg = filled_opening_order['orderLegCollection'][0]
    side = "SELL_TO_CLOSE" if opening_leg['instruction'] == "BUY_TO_OPEN" else "BUY_TO_CLOSE"
    quantity = opening_leg['quantity']
    option_type = opening_leg['instrument']['putCall']

    print(f"\n[CLOSING] Fetching latest quote to determine initial closing price...")
    chain_response = client.get_option_chains(symbol=args.symbol, strike=args.strike, fromDate=args.expiry, toDate=args.expiry, contractType=option_type)
    if not chain_response.get('success') or not chain_response.get('data'):
        print("[CLOSING] Error: Could not fetch latest quote for closing order. Aborting.")
        return {'status': 'FAILED'}
    try:
        exp_map_key = 'callExpDateMap' if option_type == 'CALL' else 'putExpDateMap'
        date_key = next(iter(chain_response['data'][exp_map_key]))
        option_data = chain_response['data'][exp_map_key][date_key][str(float(args.strike))][0]
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
    if not rules['dryrun']:
        order_response = client.place_option_order(
            account_id=account_hash, symbol=args.symbol, option_type=option_type,
            expiration_date=args.expiry, strike_price=args.strike, quantity=quantity,
            side=side, order_type="LIMIT", price=initial_price)
        if not order_response.get('success'):
            print(f"[CLOSING] Error placing closing order: {order_response.get('error')}")
            return {'status': 'FAILED'}
        current_order_id = order_response.get('data', {}).get('order_id')
        print(f"[CLOSING] Initial order placed. Order ID: {current_order_id}")
    else:
        current_order_id = f"dryrun-close-{int(time.time())}"
        print(f"[DRY RUN] [CLOSING] Simulated Order ID: {current_order_id}")

    closing_start_time = time.time()
    last_replacement_time = time.time()
    price_generator = create_price_generator(initial_price, rules['closepricefish'], rules['closepricemethod'], side)
    current_price = initial_price
    while time.time() - closing_start_time < rules['closingmaxtime']:
        if not rules['dryrun']:
            details_response = client.get_option_order_details(account_id=account_hash, order_id=current_order_id)
            if details_response.get('success'):
                status = details_response.get('data', {}).get('status')
                if status == 'FILLED':
                    print(f"\n[CLOSING] SUCCESS: Order {current_order_id} filled!")
                    return {'status': 'CLOSED', 'order': details_response.get('data')}
                elif status in ['CANCELED', 'REJECTED', 'EXPIRED']:
                    print(f"\n[CLOSING] Order {current_order_id} is dead ({status}). Aborting.")
                    return {'status': 'FAILED'}
        if time.time() - last_replacement_time > rules['closeretrytime']:
            new_price = next(price_generator)
            if abs(new_price - current_price) > 0.001:
                current_price = new_price
                replace_msg = f"[CLOSING] Replacing order with new price: {current_price:.2f}"
                print(f"\n{replace_msg}")
                if not rules['dryrun']:
                    replace_response = client.replace_option_order(
                        account_id=account_hash, order_id=current_order_id, symbol=args.symbol,
                        option_type=option_type, expiration_date=args.expiry, strike_price=args.strike,
                        quantity=quantity, side=side, order_type="LIMIT", price=current_price)
                    if replace_response.get('success'):
                        new_order_id = replace_response.get('data', {}).get('new_order_id')
                        print(f"[CLOSING] Replacement successful. New Order ID: {new_order_id}")
                        current_order_id = new_order_id
                    else:
                        print(f"[CLOSING] Error replacing closing order: {replace_response.get('error')}")
                else:
                    current_order_id = f"dryrun-close-replace-{int(time.time())}"
                    print(f"[DRY RUN] [CLOSING] Simulated New Order ID: {current_order_id}")
                last_replacement_time = time.time()

        status_msg = f"[CLOSING] Monitoring order {current_order_id} at price {current_price:.2f}..."
        print(f"  {status_msg}", end='\r')
        time.sleep(5)

    print(f"\n[CLOSING] Timed out after {rules['closingmaxtime']}s. Cancelling order.")
    if not rules['dryrun']:
        client.cancel_option_order(account_id=account_hash, order_id=current_order_id)
    else:
        print(f"[DRY RUN] [CLOSING] Would have cancelled order {current_order_id}")
    return {'status': 'TIMEOUT'}

def print_bold(text):
    """Prints text in bold using ANSI escape codes."""
    print(f"\033[1m{text}\033[0m")

def handle_emergency_close(client, account_hash, args, rules, filled_opening_order):
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
    if not rules['dryrun']:
        order_response = client.place_option_order(
            account_id=account_hash, symbol=args.symbol, option_type=option_type,
            expiration_date=args.expiry, strike_price=args.strike, quantity=quantity,
            side=side, order_type="LIMIT", price=break_even_price)
        if not order_response.get('success'):
            print_bold(f"[EMERGENCY] CRITICAL ERROR: Failed to place emergency close order: {order_response.get('error')}")
            return {'status': 'UNCLOSED'}
        current_order_id = order_response.get('data', {}).get('order_id')
        print(f"[EMERGENCY] Order placed. Order ID: {current_order_id}")
    else:
        current_order_id = f"dryrun-emergency-{int(time.time())}"
        print(f"[DRY RUN] [EMERGENCY] Simulated Order ID: {current_order_id}")

    emergency_start_time = time.time()
    while time.time() - emergency_start_time < rules['emergencyclosetime']:
        if not rules['dryrun']:
            details_response = client.get_option_order_details(account_id=account_hash, order_id=current_order_id)
            if details_response.get('success') and details_response.get('data', {}).get('status') == 'FILLED':
                print(f"\n[EMERGENCY] SUCCESS: Order {current_order_id} filled!")
                return {'status': 'CLOSED_EMERGENCY', 'order': details_response.get('data')}

        status_msg = f"[EMERGENCY] Monitoring order {current_order_id}..."
        print(f"  {status_msg}", end='\r')
        time.sleep(5)

    print("\n" + "="*60)
    print_bold("!!! [EMERGENCY] CRITICAL FAILURE: UNABLE TO CLOSE POSITION AUTOMATICALLY !!!")
    print_bold("MANUAL INTERVENTION REQUIRED IMMEDIATELY.")
    print("="*60)
    print_bold("Position Details:")
    print_bold(f"  Symbol: {args.symbol.upper()}")
    print_bold(f"  Type:   {quantity} {option_type} @ Strike {args.strike} Expiring {args.expiry}")
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

def run_bot(args, rules):
    """
    The main bot logic, containing the full state machine.
    """
    print("\nConfiguration:")
    print(f"  Symbol: {args.symbol}")
    print(f"  Strike: {args.strike if args.strike else 'Default (to be determined)'}")
    print(f"  Expiry: {args.expiry if args.expiry else 'Default (to be determined)'}")
    print("  Rules:")
    for key, value in rules.items():
        print(f"    {key}: {value}")
    print("-" * 20)

    with SchwabClient() as client:
        account_hash = get_account_hash(client)
        if not account_hash:
            return

        if not args.strike or not args.expiry:
            print("[SETUP] Strike or expiry not provided, fetching defaults...")
            quotes_response = client.get_quotes(symbols=[args.symbol])
            if not quotes_response.get('success') or not quotes_response.get('data'):
                print(f"[SETUP] Error: Could not retrieve quote for {args.symbol} to determine defaults. Exiting.")
                return
            try:
                quote_string = quotes_response['data'][0]
                last_price = float(quote_string.split()[1])
                print(f"[SETUP] Current price for {args.symbol}: {last_price:.2f}")
            except (ValueError, IndexError):
                print(f"[SETUP] Error: Could not parse last price for {args.symbol}. Exiting.")
                return
            if not args.strike:
                args.strike = get_nearest_strike(last_price)
                print(f"[SETUP] Using default strike: {args.strike:.2f}")
            if not args.expiry:
                args.expiry = get_next_friday()
                print(f"[SETUP] Using default expiry: {args.expiry}")

        print("\nFinal Configuration:")
        print(f"  Strike: {args.strike:.2f}")
        print(f"  Expiry: {args.expiry}")
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
                if rules['dryrun']: print("[DRY RUN] [SEARCHING] Simulating fetch.")
                option_chain_response = client.get_option_chains(symbol=args.symbol, strike=args.strike, fromDate=args.expiry, toDate=args.expiry, contractType='ALL')
                if not option_chain_response.get('success') or not option_chain_response.get('data'):
                    print(f"[SEARCHING] Error: Could not retrieve option chain: {option_chain_response.get('error')}")
                    time.sleep(5)
                    continue
                option_chain_data = option_chain_response.get('data', {})
                call_map = option_chain_data.get('callExpDateMap', {})
                put_map = option_chain_data.get('putExpDateMap', {})
                call_data, put_data = None, None
                date_key_call = next((k for k in call_map if k.startswith(args.expiry)), None)
                if date_key_call:
                    call_data = call_map.get(date_key_call, {}).get(str(float(args.strike)), [None])[0]
                date_key_put = next((k for k in put_map if k.startswith(args.expiry)), None)
                if date_key_put:
                    put_data = put_map.get(date_key_put, {}).get(str(float(args.strike)), [None])[0]
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
                opening_result = handle_opening_state(client, account_hash, args, rules, selected_option)
                if opening_result.get('status') == 'FILLED':
                    print("\n[STATE_TRANSITION] Opening Order Filled. Entering Closing State.")
                    closing_result = handle_closing_state(client, account_hash, args, rules, opening_result.get('order'))
                    if closing_result.get('status') == 'CLOSED':
                        print("\n[COMPLETE] TRADE COMPLETE: Closing order filled successfully!")
                        print_trade_summary(opening_result.get('order'), closing_result.get('order'))
                        break
                    elif closing_result.get('status') == 'TIMEOUT':
                        print("\n[STATE_TRANSITION] Closing state timed out. Entering Emergency Close.")
                        emergency_result = handle_emergency_close(client, account_hash, args, rules, opening_result.get('order'))
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
    parser.add_argument("--strike", type=float, help="The strike price. Defaults to the nearest strike.")
    parser.add_argument("--expiry", help="The expiry date (YYYY-MM-DD). Defaults to the next Friday.")
    parser.add_argument("--dry-run", action="store_true", help="Run the bot without placing any real orders.")
    args = parser.parse_args()

    print("=============================================")
    print("         noni1aj - Trading Bot         ")
    print("=============================================")
    print(f"[{datetime.now().strftime('%Y-%m-%d %H:%M:%S')}] - Starting bot for symbol: {args.symbol}")

    rules_file = args.rules_file or f"{args.symbol.lower()}-rules.yml"
    rules = load_and_validate_rules(rules_file)

    if args.dry_run:
        print("\n*** DRY RUN MODE ENABLED - NO ORDERS WILL BE PLACED ***\n")
        rules['dryrun'] = True

    run_bot(args, rules)
