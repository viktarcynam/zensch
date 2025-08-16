from flask import Flask, jsonify, request, render_template
import sys
import os
from datetime import datetime, timedelta
import time
import threading
import json

# Add the parent directory to the Python path to import the client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client import SchwabClient
from trading_utils import parse_option_symbol, get_nearest_strike, get_next_friday, parse_option_position_details, \
    find_replacement_order, parse_instrument_description

app = Flask(__name__)

# --- Thread-Safe State and Cache Management ---
ACTIVE_ORDERS = {}
INTERESTED_INSTRUMENTS = {}
DATA_CACHE = {
    'quotes': {}, 'positions': {}, 'order_statuses': {}, 'account_hashes': []
}
CACHE_LOCK = threading.Lock()
FAST_MODE_UNTIL = 0

def background_poller():
    """
    This function runs in a background thread and periodically fetches data
    from the Schwab API to keep the local cache fresh.
    It uses a simplified, robust state management model.
    """
    app.logger.info("Background poller started.")
    global FAST_MODE_UNTIL, ACTIVE_ORDERS, DATA_CACHE

    while True:
        primary_account_hash = None
        with CACHE_LOCK:
            # Check if we have an account hash, otherwise we can't do anything.
            if DATA_CACHE.get('account_hashes'):
                primary_account_hash = DATA_CACHE['account_hashes'][0].get('hashValue')

        if not primary_account_hash:
            # If no account hash, try to get one
            with SchwabClient() as client:
                acc_response = client.get_linked_accounts()
                if acc_response.get('success'):
                    with CACHE_LOCK:
                        DATA_CACHE['account_hashes'] = acc_response.get('data', [])
            time.sleep(5) # Wait before retrying
            continue

        # Determine polling speed
        is_active = bool(ACTIVE_ORDERS) or (time.time() < FAST_MODE_UNTIL)
        sleep_duration = 1.5 if is_active else 3.0

        # --- Main Polling Logic ---
        with SchwabClient() as client:
            # 1. Get all currently working and pending orders from the API.
            # This is the single source of truth for what is active.
            all_working_orders = []
            from_time = (datetime.now() - timedelta(days=30)).isoformat() + "Z"
            for status in ['WORKING', 'PENDING_ACTIVATION']:
                response = client.get_option_orders(
                    account_id=primary_account_hash,
                    status=status,
                    from_entered_time=from_time
                )
                if response.get('success'):
                    all_working_orders.extend(response.get('data', []))
                else:
                    app.logger.warning(f"Poller failed to get '{status}' orders.")

            # 2. Rebuild the ACTIVE_ORDERS cache from scratch based on the API response.
            new_active_orders = {}
            for order in all_working_orders:
                order_id = order.get('orderId')
                leg = order.get('orderLegCollection', [{}])[0]
                instrument = leg.get('instrument', {})

                # Standardize the order details into a consistent format.
                order_details = {
                    "account_id": primary_account_hash,
                    "order_id": order_id,
                    "symbol": instrument.get('underlyingSymbol'),
                    "option_type": instrument.get('putCall'),
                    "quantity": leg.get('quantity'),
                    "side": leg.get('instruction'),
                    "order_type": order.get('orderType'),
                    "price": order.get('price')
                }
                # Parse description for expiry and strike as a fallback
                parsed_desc = parse_instrument_description(instrument.get('description'))
                if parsed_desc:
                    order_details['expiration_date'] = parsed_desc.get('expiry')
                    order_details['strike_price'] = parsed_desc.get('strike')

                new_active_orders[order_id] = order_details

            # 3. Atomically update the global state and poll for statuses.
            with CACHE_LOCK:
                ACTIVE_ORDERS = new_active_orders
                # Also, fetch detailed status for each currently active order
                for order_id in ACTIVE_ORDERS.keys():
                    status_response = client.get_option_order_details(
                        account_id=primary_account_hash,
                        order_id=order_id
                    )
                    if status_response.get('success'):
                        DATA_CACHE['order_statuses'][order_id] = status_response.get('data', {})
                    else:
                        app.logger.warning(f"Poller failed to get status for order {order_id}")

                # Optional: Fetch positions, quotes etc.
                positions_response = client.get_positions(account_hash=primary_account_hash)
                if positions_response.get('success'):
                    DATA_CACHE['positions'] = positions_response.get('data')

        time.sleep(sleep_duration)


# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    with CACHE_LOCK:
        if DATA_CACHE['account_hashes']:
            return jsonify({"success": True, "account_hash": DATA_CACHE['account_hashes'][0].get('hashValue')})
    with SchwabClient() as client:
        accounts = client.get_linked_accounts()
        if accounts and accounts.get('success'):
            account_list = accounts.get('data', [])
            if account_list:
                with CACHE_LOCK:
                    DATA_CACHE['account_hashes'] = account_list
                return jsonify({"success": True, "account_hash": account_list[0].get('hashValue')})
    return jsonify({"success": False, "error": "Could not retrieve account hash."}), 500

@app.route('/api/defaults/<symbol>', methods=['GET'])
def get_defaults(symbol):
    with SchwabClient() as client:
        quotes_response = client.get_quotes(symbols=[symbol.upper()])
        if quotes_response.get('success') and quotes_response.get('data'):
            try:
                last_price = float(quotes_response['data'][0].split()[1])
                return jsonify({"success": True, "strike": get_nearest_strike(last_price), "expiry": get_next_friday(), "price": last_price})
            except (ValueError, IndexError):
                return jsonify({"success": False, "error": "Could not parse last price."}), 500
    return jsonify({"success": False, "error": f"Could not retrieve quote for {symbol}."}), 404


@app.route('/api/strikes/<symbol>/<expiry>', methods=['GET'])
def get_strikes(symbol, expiry):
    """
    Fetches a list of valid strike prices for a given symbol and expiration.
    Also returns the underlying price to help the frontend select a default.
    """
    with SchwabClient() as client:
        # Use strikeCount to get a range of strikes around the current price
        chain_response = client.get_option_chains(
            symbol=symbol.upper(),
            contractType='ALL',
            strikeCount=20,
            fromDate=expiry,
            toDate=expiry,
            includeUnderlyingQuote=True  # Make sure we get the price
        )

    if not chain_response.get('success'):
        return jsonify({"success": False, "error": "Failed to retrieve option chain from server."}), 500

    data = chain_response.get('data', {})
    if data.get('status') != 'SUCCESS':
        return jsonify({"success": False, "error": f"API Error: {data.get('status')}"}), 500

    all_strikes = set()

    # The API returns strikes as keys in a map. We extract from both calls and puts.
    call_map = data.get('callExpDateMap', {})
    if call_map:
        # The key is the actual expiration date string, e.g., "2025-09-19:35"
        # We just need the first (and only) one.
        date_key = next(iter(call_map))
        for strike in call_map[date_key]:
            all_strikes.add(float(strike))

    put_map = data.get('putExpDateMap', {})
    if put_map:
        date_key = next(iter(put_map))
        for strike in put_map[date_key]:
            all_strikes.add(float(strike))

    if not all_strikes:
        return jsonify({"success": False, "error": "No strikes found for the given expiry."}), 404

    sorted_strikes = sorted(list(all_strikes))
    return jsonify({
        "success": True,
        "strikes": sorted_strikes,
        "underlying_price": data.get('underlyingPrice')
    })


@app.route('/api/positions/<symbol>', methods=['GET'])
def get_positions(symbol):
    account_hash = request.args.get('account_hash')
    if not account_hash: return jsonify({"success": False, "error": "Account hash required."}), 400
    with SchwabClient() as client:
        positions_response = client.get_positions_by_symbol(symbol=symbol.upper(), account_hash=account_hash)
    if not (positions_response.get('success') and positions_response.get('data')):
        return jsonify({"success": False, "error": "Failed to retrieve positions via API."}), 500
    clean_positions = []
    accounts = positions_response.get('data', {}).get('accounts', [])
    for acc in accounts:
        for pos in acc.get('positions', []):
            asset_type = pos.get('assetType')
            qty = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
            if qty == 0: continue
            position_data = {'asset_type': asset_type, 'quantity': qty, 'average_price': pos.get('averagePrice', 0.0)}
            instrument = pos.get('instrument', {})
            if asset_type == 'EQUITY':
                position_data['symbol'] = instrument.get('symbol')
                clean_positions.append(position_data)
            elif asset_type == 'OPTION':
                details = parse_option_position_details(pos)
                if details:
                    position_data.update({'put_call': details.get('put_call'), 'strike': details.get('strike'), 'expiry': details.get('expiry')})
                    clean_positions.append(position_data)
    return jsonify({"success": True, "positions": clean_positions})

@app.route('/api/recent_fills', methods=['GET'])
def get_recent_fills():
    account_hash = request.args.get('account_hash')
    if not account_hash: return jsonify({"success": False, "error": "Account hash required."}), 400
    with SchwabClient() as client:
        # Fetch fills from the last 2 days up to the current time.
        from_date = datetime.now() - timedelta(days=2)
        from_date_str = from_date.strftime('%Y-%m-%d')
        orders_response = client.get_option_orders(
            account_id=account_hash,
            status='FILLED',
            from_entered_time=f"{from_date_str}T00:00:00Z"
        )
        if orders_response.get('success') and orders_response.get('data'):
            filled_orders_data = []
            for order in orders_response.get('data', []):
                try:
                    leg = order['orderLegCollection'][0]
                    instrument = leg.get('instrument', {})
                    activity = order['orderActivityCollection'][0]['executionLegs'][0]

                    quantity = leg.get('quantity', 0)
                    instruction = leg.get('instruction', '')
                    if 'SELL' in instruction.upper():
                        quantity = -quantity

                    parsed_symbol = parse_option_symbol(instrument.get('symbol'))
                    if not parsed_symbol:
                        continue

                    strike = parsed_symbol.get('strike')
                    expiry_date_str = parsed_symbol.get('expiry_date')

                    fill_object = {
                        "quantity": quantity,
                        "putCall": instrument.get('putCall', ' ')[0],
                        "symbol": instrument.get('underlyingSymbol'),
                        "strike": strike,
                        "expiry": expiry_date_str,
                        "price": activity.get('price')
                    }
                    filled_orders_data.append(fill_object)
                except (IndexError, KeyError, TypeError, ValueError) as e:
                    app.logger.error(f"Error parsing recent fill: {e} - Order: {order}")
                    continue
            return jsonify({"success": True, "fills": filled_orders_data})
    return jsonify({"success": False, "error": "Could not retrieve recent fills."}), 500


@app.route('/api/working_orders', methods=['GET'])
def get_working_orders():
    """
    Returns a list of all active orders from the in-memory cache,
    which is maintained by the background poller.
    """
    with CACHE_LOCK:
        # The ACTIVE_ORDERS dict values are the order details objects.
        # The poller already includes both WORKING and PENDING_ACTIVATION orders.
        orders = list(ACTIVE_ORDERS.values())
    return jsonify({"success": True, "orders": orders})


@app.route('/api/options/<symbol>/<strike>/<expiry>', methods=['GET'])
def get_options(symbol, strike, expiry):
    with SchwabClient() as client:
        chain_response = client.get_option_chains(
            symbol=symbol.upper(),
            strike=float(strike),
            fromDate=expiry,
            toDate=expiry,
            contractType='ALL',
            includeUnderlyingQuote=True
        )
        if chain_response.get('success'):
            return jsonify({"success": True, "data": chain_response.get('data', {})})
    return jsonify({"success": False, "error": "Could not retrieve option chain."}), 500

@app.route('/api/instrument_position', methods=['GET'])
def get_instrument_position():
    account_hash = request.args.get('account_hash')
    symbol = request.args.get('symbol')
    strike = float(request.args.get('strike'))
    expiry = request.args.get('expiry')
    if not all([account_hash, symbol, strike, expiry]):
        return jsonify({"success": False, "error": "Missing params"}), 400
    with SchwabClient() as client:
        positions_response = client.get_positions_by_symbol(symbol=symbol.upper(), account_hash=account_hash)
    if positions_response.get('success') and positions_response.get('data'):
        call_qty, put_qty = 0, 0
        accounts = positions_response.get('data', {}).get('accounts', [])
        for acc in accounts:
            for pos in acc.get('positions', []):
                details = parse_option_position_details(pos)
                if details and abs(details['strike'] - strike) < 0.001 and details['expiry'] == expiry:
                    if details['put_call'] == 'CALL':
                        call_qty = details.get('quantity', 0)
                    elif details['put_call'] == 'PUT':
                        put_qty = details.get('quantity', 0)
        return jsonify({"success": True, "call_quantity": call_qty, "put_quantity": put_qty})
    return jsonify({"success": False, "error": "Failed to retrieve instrument position via API."}), 500

@app.route('/api/order', methods=['POST'])
def handle_order():
    data = request.json
    details = data.get('order_details', {})
    if not details:
        return jsonify({"success": False, "error": "Missing order_details"}), 400

    global FAST_MODE_UNTIL

    # Check for an existing order for the same instrument to replace
    existing_order_to_replace = None
    with CACHE_LOCK:
        for order_id, active_order in ACTIVE_ORDERS.items():
            # Match on the core instrument details, but not price
            if (active_order.get('symbol') == details.get('symbol') and
                active_order.get('option_type') == details.get('option_type') and
                active_order.get('strike_price') == details.get('strike_price') and
                active_order.get('expiration_date') == details.get('expiration_date')):

                # We found a candidate to replace
                existing_order_to_replace = active_order
                break

    with SchwabClient() as client:
        if existing_order_to_replace:
            # --- We are replacing an existing order ---
            app.logger.info(f"Found existing order {existing_order_to_replace['order_id']}. Replacing it.")

            # Per user requirements, retain the original order's quantity and side for the replacement.
            # The price is the only thing that should change from the user's new input.
            original_quantity = existing_order_to_replace['quantity']
            original_side = existing_order_to_replace['side']
            app.logger.info(f"Retaining original quantity ({original_quantity}) and side ({original_side}) for replacement.")

            response = client.replace_option_order(
                account_id=details['account_id'],
                order_id=existing_order_to_replace['order_id'],
                symbol=details['symbol'],
                option_type=details['option_type'],
                expiration_date=details['expiration_date'],
                strike_price=details['strike_price'],
                quantity=original_quantity,  # Use original quantity
                side=original_side,          # Use original side
                order_type=details['order_type'],
                price=details.get('price')
            )
            # If the replace call was successful, immediately remove the old order from the cache
            # to prevent the frontend from polling for an invalid ID.
            if response.get('success'):
                with CACHE_LOCK:
                    old_order_id = existing_order_to_replace['order_id']
                    if old_order_id in ACTIVE_ORDERS:
                        del ACTIVE_ORDERS[old_order_id]
                        app.logger.info(f"Immediately removed replaced order {old_order_id} from active cache.")
        else:
            # --- We are placing a new order ---
            app.logger.info("No existing order found. Placing a new order.")
            response = client.place_option_order(**details)

        if response.get('success'):
            with CACHE_LOCK:
                FAST_MODE_UNTIL = time.time() + 30
            app.logger.info(f"Order request successful. Response: {response.get('data')}")
            return jsonify({"success": True})

    return jsonify({"success": False, "error": response.get('error', 'Unknown error')}), 500

@app.route('/api/cancel_order', methods=['POST'])
def cancel_order():
    data = request.json
    order_id = data.get('order_id')
    account_id = data.get('account_id')
    if not order_id or not account_id:
        return jsonify({"success": False, "error": "Missing order_id or account_id"}), 400
    with SchwabClient() as client:
        response = client.cancel_option_order(account_id=account_id, order_id=order_id)
        if response.get('success'):
            return jsonify({"success": True})
    return jsonify({"success": False, "error": response.get('error')}), 500

@app.route('/api/get_instrument_orders', methods=['GET'])
def get_instrument_orders():
    symbol = request.args.get('symbol')
    strike_str = request.args.get('strike')
    expiry = request.args.get('expiry')

    if not all([symbol, strike_str, expiry]):
        return jsonify({"success": False, "error": "Missing params", "orders": []}), 400
    try:
        strike = float(strike_str)
    except (ValueError, TypeError):
        return jsonify({"success": False, "error": "Invalid strike price", "orders": []}), 400

    found_orders = []
    with CACHE_LOCK:
        for order_id, order_details in ACTIVE_ORDERS.items():
            if (order_details.get('symbol', '').upper() == symbol.upper() and
                order_details.get('strike_price') == strike and
                order_details.get('expiration_date') == expiry):

                status_data = DATA_CACHE.get('order_statuses', {}).get(order_id, {})
                order_info = {
                    "order_id": order_id,
                    "account_id": order_details.get('account_id'),
                    "type": order_details.get('option_type'),
                    "status": status_data.get('status', 'UNKNOWN'),
                    "side": order_details.get('side'),
                    "quantity": order_details.get('quantity'),
                    "price": order_details.get('price')
                }
                found_orders.append(order_info)
    return jsonify({"success": True, "orders": found_orders})


@app.route('/api/request_history/<symbol>', methods=['POST'])
def request_history(symbol):
    """
    Endpoint to trigger a non-blocking request to fetch and cache historical data for a symbol.
    """
    if not symbol:
        return jsonify({"success": False, "error": "Symbol is required"}), 400

    with SchwabClient() as client:
        response = client.request_history(symbol)

    if response.get('success'):
        return jsonify(response), 200
    else:
        return jsonify(response), 500


@app.route('/api/get_history/<symbol>', methods=['GET'])
def get_history(symbol):
    """
    Endpoint to retrieve cached historical data for a symbol.
    """
    if not symbol:
        return jsonify({"success": False, "error": "Symbol is required"}), 400

    with SchwabClient() as client:
        response = client.get_history(symbol)

    if response.get('success'):
        return jsonify(response), 200
    else:
        # Return 404 if the specific error is 'No history found'
        if "No history found" in response.get('error', ''):
            return jsonify(response), 404
        return jsonify(response), 500


if __name__ == '__main__':
    # Start the background poller thread
    poller_thread = threading.Thread(target=background_poller, daemon=True)
    poller_thread.start()
    # Start the Flask app
    app.run(port=5001, debug=True)
