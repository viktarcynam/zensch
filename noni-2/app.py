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

# ACTIVE_ORDERS stores the details of orders we are actively monitoring.
# The key is the order_id, and the value is a dictionary of its details.
ACTIVE_ORDERS = {}

# INTERESTED_INSTRUMENTS stores a "watchlist" of instruments the user is
# currently viewing in the UI, keyed by a unique section_id from the frontend.
INTERESTED_INSTRUMENTS = {}

# DATA_CACHE stores the latest data fetched from the API.
# This is what the frontend will read from, making it fast and reducing API calls.
DATA_CACHE = {
    'quotes': {},          # Key: symbol, Value: quote data
    'positions': {},       # Key: account_hash, Value: position data
    'order_statuses': {},  # Key: order_id, Value: order status data
    'account_hashes': []   # List of available account hashes
}
CACHE_LOCK = threading.Lock()
FAST_MODE_UNTIL = 0  # A timestamp until which fast mode is active


def background_poller():
    """
    This function runs in a background thread and periodically fetches data
    from the Schwab API to keep the local cache fresh.
    """
    app.logger.info("Background poller started.")
    global FAST_MODE_UNTIL

    while True:
        sleep_duration = 3.0  # Default to idle
        with SchwabClient() as client:
            with CACHE_LOCK:
                now = time.time()
                is_active = bool(ACTIVE_ORDERS)

                # Determine if we are in fast mode
                in_fast_mode = is_active or (now < FAST_MODE_UNTIL)

                # If an order just became active (i.e., we were not active before, but are now),
                # ensure fast mode is enabled for at least 30 seconds.
                if is_active and not DATA_CACHE.get('was_active', False):
                    FAST_MODE_UNTIL = now + 30
                    app.logger.info("Active order detected. Entering fast poll mode for 30s.")

                DATA_CACHE['was_active'] = is_active


                if in_fast_mode:
                    sleep_duration = 1.5
                else:
                    sleep_duration = 3.0

                # If idle, just refresh accounts and continue
                if not in_fast_mode:
                    acc_response = client.get_linked_accounts()
                    if acc_response.get('success'):
                        DATA_CACHE['account_hashes'] = acc_response.get('data', [])

                    time.sleep(sleep_duration)
                    continue

                # --- Main Polling Logic (Fast Mode) ---
                primary_account_hash = DATA_CACHE.get('account_hashes', [{}])[0].get('hashValue')
                if not primary_account_hash:
                    app.logger.warning("Poller: No account hash available to fetch data.")
                    time.sleep(sleep_duration)
                    continue

                # 1. Always fetch positions for the primary account
                positions_response = client.get_positions(account_hash=primary_account_hash)
                if positions_response.get('success'):
                    DATA_CACHE['positions'][primary_account_hash] = positions_response.get('data')
                else:
                    app.logger.warning(f"Poller failed to get positions for {primary_account_hash}")

                # 2. Auto-discover externally placed orders

                # 2. Auto-discover externally placed orders
                all_active_orders = []
                # Fetch orders with both 'WORKING' and 'PENDING_ACTIVATION' statuses
                for status in ['WORKING', 'PENDING_ACTIVATION']:
                    response = client.get_option_orders(account_id=primary_account_hash, status=status)
                    if response.get('success'):
                        all_active_orders.extend(response.get('data', []))
                    else:
                        app.logger.warning(f"Poller failed to get '{status}' orders for auto-discovery.")

                if all_active_orders:
                    # This is the original logic, which we will now run on the fetched orders
                    for order in all_active_orders:
                        order_id = order.get('orderId')
                        if order_id in ACTIVE_ORDERS:
                            continue # Already tracking this one

                        # Parse the instrument details from the order
                        leg = order.get('orderLegCollection', [{}])[0]
                        instrument = leg.get('instrument', {})
                        if not instrument: continue

                        try:
                            order_symbol = instrument.get('underlyingSymbol')
                            order_put_call = instrument.get('putCall')
                            description = instrument.get('description')

                            if not description:
                                continue

                            # Use the new, reliable description parser
                            parsed_details = parse_instrument_description(description)

                            if not parsed_details:
                                app.logger.warning(f"Could not parse instrument description for auto-discovery: {description}")
                                continue

                            order_expiry = parsed_details['expiry']
                            order_strike = parsed_details['strike']

                            # Now, compare with our watchlist of interested instruments
                            for interested in INTERESTED_INSTRUMENTS.values():
                                # Ensure all keys exist before comparing
                                if all(k in interested for k in ['symbol', 'strike', 'expiry']):
                                    if (interested['symbol'].upper() == order_symbol and
                                        abs(interested['strike'] - order_strike) < 0.001 and
                                        interested['expiry'] == order_expiry):

                                        app.logger.info(f"Auto-discovered external order {order_id} for {order_symbol} via description. Adding to active monitoring.")
                                        # Add it to ACTIVE_ORDERS so we can start tracking it
                                        ACTIVE_ORDERS[order_id] = {
                                            "account_id": primary_account_hash,
                                            "symbol": order_symbol,
                                            "option_type": order_put_call,
                                            "expiration_date": order_expiry,
                                            "strike_price": order_strike,
                                            "quantity": leg.get('quantity'),
                                            "side": leg.get('instruction'),
                                            "order_type": order.get('orderType'),
                                            "price": order.get('price')
                                        }
                                        # Found a match, no need to check other watchlist items for this order
                                        break
                        except (KeyError, TypeError) as e:
                            app.logger.error(f"Error processing discovered order {order_id}: {e}")
                            continue # Move to the next order

                # 3. Collect all unique symbols from active orders for quote fetching
                if ACTIVE_ORDERS:
                    symbols_to_poll = set(order['symbol'] for order in ACTIVE_ORDERS.values())
                    if symbols_to_poll:
                        quotes_response = client.get_quotes(symbols=list(symbols_to_poll))
                        if quotes_response.get('success') and quotes_response.get('data'):
                            # Assuming get_quotes returns a list of strings
                            for quote_str in quotes_response['data']:
                                parts = quote_str.split()
                                if len(parts) > 1:
                                    symbol = parts[0]
                                    DATA_CACHE['quotes'][symbol] = quote_str # Store raw string for now
                        else:
                            app.logger.warning(f"Poller failed to get quotes: {quotes_response.get('error')}")

                # 4. Fetch status for each active order
                # Make a copy of keys to avoid issues with dict size changing during iteration
                for order_id, order_details in list(ACTIVE_ORDERS.items()):
                    status_response = client.get_option_order_details(
                        account_id=order_details['account_id'],
                        order_id=order_id
                    )
                    if status_response.get('success'):
                        status_data = status_response.get('data', {})
                        DATA_CACHE['order_statuses'][order_id] = status_data
                        # If order is terminal, remove it from active monitoring
                        if status_data.get('status') in ['FILLED', 'CANCELED', 'EXPIRED', 'REJECTED']:
                            app.logger.info(f"Order {order_id} reached terminal state '{status_data.get('status')}'. Removing from active polling.")
                            if order_id in ACTIVE_ORDERS:
                                del ACTIVE_ORDERS[order_id]
                    else:
                        app.logger.warning(f"Poller failed to get status for order {order_id}")

        time.sleep(sleep_duration)


# --- Flask Routes ---
# These routes will now primarily read from the DATA_CACHE for speed.

@app.route('/')
def index():
    return render_template('index.html')


@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    with CACHE_LOCK:
        # Serve from cache if available, otherwise fetch
        if DATA_CACHE['account_hashes']:
            return jsonify({"success": True, "account_hash": DATA_CACHE['account_hashes'][0].get('hashValue')})

    # Fallback to direct call if cache is empty on first load
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
    # This can remain a direct call as it's on-demand
    with SchwabClient() as client:
        quotes_response = client.get_quotes(symbols=[symbol.upper()])
        if quotes_response.get('success') and quotes_response.get('data'):
            try:
                last_price = float(quotes_response['data'][0].split()[1])
                return jsonify({"success": True, "strike": get_nearest_strike(last_price), "expiry": get_next_friday(), "price": last_price})
            except (ValueError, IndexError):
                return jsonify({"success": False, "error": "Could not parse last price."}), 500
    return jsonify({"success": False, "error": f"Could not retrieve quote for {symbol}."}), 404


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
            if qty == 0:
                continue

            position_data = {
                'asset_type': asset_type,
                'quantity': qty,
                'average_price': pos.get('averagePrice', 0.0)
            }

            instrument = pos.get('instrument', {})
            if asset_type == 'EQUITY':
                position_data['symbol'] = instrument.get('symbol')
                clean_positions.append(position_data)

            elif asset_type == 'OPTION':
                details = parse_option_position_details(pos)
                if details:
                    # Pass the raw details through; DTE will be calculated on the frontend.
                    position_data.update({
                        'put_call': details.get('put_call'),
                        'strike': details.get('strike'),
                        'expiry': details.get('expiry'),
                    })
                    clean_positions.append(position_data)

    return jsonify({"success": True, "positions": clean_positions})


@app.route('/api/recent_fills', methods=['GET'])
def get_recent_fills():
    # This remains a direct call as it's a specific historical query
    account_hash = request.args.get('account_hash')
    if not account_hash: return jsonify({"success": False, "error": "Account hash required."}), 400
    with SchwabClient() as client:
        today_str = datetime.now().strftime('%Y-%m-%d')
        orders_response = client.get_option_orders(account_id=account_hash, status='FILLED', from_entered_time=f"{today_str}T00:00:00Z", to_entered_time=f"{today_str}T23:59:59Z")
        if orders_response.get('success') and orders_response.get('data'):
            fills_strings = []
            for order in orders_response.get('data', []):
                try:
                    leg = order['orderLegCollection'][0]
                    activity = order['orderActivityCollection'][0]['executionLegs'][0]
                    fills_strings.append(f"{leg['quantity']:+g}{leg['instrument']['putCall'][0]} {leg['instrument']['underlyingSymbol']} {activity['price']:.2f}")
                except (IndexError, KeyError):
                    continue
            return jsonify({"success": True, "fills": fills_strings})
    return jsonify({"success": False, "error": "Could not retrieve recent fills."}), 500


@app.route('/api/options/<symbol>/<strike>/<expiry>', methods=['GET'])
def get_options(symbol, strike, expiry):
    # This also remains a direct call as it's for a specific instrument not necessarily in active orders
    with SchwabClient() as client:
        chain_response = client.get_option_chains(symbol=symbol.upper(), strike=float(strike), fromDate=expiry, toDate=expiry, contractType='ALL')
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

    # Bypassing the cache to use the reliable, pre-filtered API call. This avoids cross-instrument data contamination.
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
    global FAST_MODE_UNTIL
    with SchwabClient() as client:
        details = data['order_details']
        response = client.place_option_order(**details)
        if response.get('success'):
            order_id = response.get('data', {}).get('order_id')
            if order_id:
                with CACHE_LOCK:
                    # Add to active monitoring and trigger fast poll mode
                    ACTIVE_ORDERS[order_id] = details
                    FAST_MODE_UNTIL = time.time() + 30
                app.logger.info(f"Placed order {order_id}. Added to active monitoring and triggered fast poll mode.")
                return jsonify({"success": True, "order_id": order_id})
        return jsonify({"success": False, "error": response.get('error')}), 500


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
            with CACHE_LOCK:
                # Remove from active monitoring if it exists
                if order_id in ACTIVE_ORDERS:
                    del ACTIVE_ORDERS[order_id]
                # Also remove from cache
                if order_id in DATA_CACHE['order_statuses']:
                    del DATA_CACHE['order_statuses'][order_id]
            app.logger.info(f"Canceled order {order_id}. Removed from active monitoring.")
            return jsonify({"success": True})
    return jsonify({"success": False, "error": response.get('error')}), 500


@app.route('/api/order_status/<order_id>', methods=['GET'])
def get_order_status(order_id):
    with CACHE_LOCK:
        status_data = DATA_CACHE.get('order_statuses', {}).get(order_id)

    if status_data:
        return jsonify({"success": True, "data": status_data})

    # Fallback for when an order is very new and not yet in cache
    with CACHE_LOCK:
        if order_id in ACTIVE_ORDERS:
            account_id = ACTIVE_ORDERS[order_id]['account_id']
        else: # If it's not even in active orders, it's an unknown/old order
            return jsonify({"success": False, "error": "Order ID not being tracked or is invalid."}), 404

    with SchwabClient() as client:
        app.logger.info(f"Cache miss for order {order_id}. Fetching directly.")
        response = client.get_option_order_details(account_id=account_id, order_id=order_id)
        if response.get('success'):
            return jsonify({"success": True, "data": response.get('data', {})})

    return jsonify({"success": False, "error": "Could not get status from cache or direct fetch."}), 404


@app.route('/api/find_replacement_order', methods=['POST'])
def find_replacement_order_api():
    data = request.get_json()
    if not data: return jsonify({"success": False, "error": "Invalid JSON"}), 400

    original_order_from_js = data.get('original_order')
    account_hash = data.get('account_hash')

    if not original_order_from_js or not account_hash:
        return jsonify({"success": False, "error": "Missing params"}), 400

    # Standardize the order dictionary from JS to match the utility function's expectation
    standardized_order = {
        "orderId": original_order_from_js.get('orderId'),
        "symbol": original_order_from_js.get('symbol'),
        "putCall": original_order_from_js.get('option_type'),
        "instruction": original_order_from_js.get('side'),
        "strike": original_order_from_js.get('strike_price'),
        "expiry": original_order_from_js.get('expiration_date')
    }

    with SchwabClient() as client:
        replacement = find_replacement_order(client, account_hash, standardized_order, logger=app.logger)
        if replacement:
            # When a replacement is found, we need to update our tracking
            new_order_id = replacement.get('orderId')
            if new_order_id:
                with CACHE_LOCK:
                    global FAST_MODE_UNTIL
                    # Remove old order and add new one
                    if standardized_order['orderId'] in ACTIVE_ORDERS:
                        del ACTIVE_ORDERS[standardized_order['orderId']]
                    # The details of the new order are mostly the same, but price can change.
                    # For now, we reuse old details but can enhance later.
                    new_order_details = standardized_order.copy()
                    new_order_details['price'] = replacement.get('price')
                    ACTIVE_ORDERS[new_order_id] = new_order_details
                    FAST_MODE_UNTIL = time.time() + 30
                    app.logger.info(f"Replaced order {standardized_order['orderId']} with {new_order_id}. Updating active polling and triggering fast mode.")
            return jsonify({"success": True, "replacement_order": replacement})

    return jsonify({"success": False, "error": "Not found"}), 404


@app.route('/api/set_interested_instrument', methods=['POST'])
def set_interested_instrument():
    data = request.get_json()
    if not data or 'section_id' not in data or 'instrument' not in data:
        return jsonify({"success": False, "error": "Invalid request. Missing section_id or instrument."}), 400

    section_id = data['section_id']
    instrument = data['instrument']

    with CACHE_LOCK:
        if instrument:
            INTERESTED_INSTRUMENTS[section_id] = instrument
            app.logger.info(f"Updated instrument of interest for section {section_id}: {instrument.get('symbol')}")
        elif section_id in INTERESTED_INSTRUMENTS:
            del INTERESTED_INSTRUMENTS[section_id]
            app.logger.info(f"Cleared instrument of interest for section {section_id}")

    return jsonify({"success": True})


@app.route('/api/trigger_fast_poll', methods=['POST'])
def trigger_fast_poll():
    global FAST_MODE_UNTIL
    with CACHE_LOCK:
        FAST_MODE_UNTIL = time.time() + 30
    app.logger.info("Fast poll mode activated by frontend for 30 seconds.")
    return jsonify({"success": True, "message": "Fast poll mode activated for 30 seconds."})


@app.route('/api/log_error', methods=['POST'])
def log_error():
    data = request.get_json()
    if data and 'message' in data:
        app.logger.error(f"Frontend Error: {data['message']}")
        return jsonify({"success": True})
    return jsonify({"success": False, "error": "Invalid log message"}), 400


@app.route('/api/has_active_orders', methods=['GET'])
def has_active_orders():
    # This endpoint can now be answered directly from our state
    order_id = request.args.get('order_id')
    with CACHE_LOCK:
        has_active = order_id in ACTIVE_ORDERS
    return jsonify({"success": True, "has_active": has_active})


if __name__ == '__main__':
    # Start the background poller thread
    poller_thread = threading.Thread(target=background_poller, daemon=True)
    poller_thread.start()
    # Start the Flask app
    app.run(port=5001, debug=True)
