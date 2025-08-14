from flask import Flask, jsonify, request, render_template
import sys
import os
import uuid
from datetime import datetime, timedelta

# Add the parent directory to the Python path to import the client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client import SchwabClient
import time

app = Flask(__name__)

# --- Helper functions ---

def parse_option_symbol(symbol_string):
    """
    Parses a standard OCC option symbol string.
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
        app.logger.error(f"Error parsing OCC symbol '{symbol_string}': {e}")
        return None

def find_replacement_order(client, account_hash, original_order):
    """
    Finds the new order that replaced an old one.
    """
    original_order_id = original_order['orderId']
    app.logger.info(f"Searching for replacement of order {original_order_id}...")
    max_retries = 3
    retry_delay = 2
    for attempt in range(max_retries):
        if attempt > 0:
            app.logger.info(f"Retrying search... (Attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)
        working_statuses = ['WORKING', 'PENDING_ACTIVATION', 'ACCEPTED', 'QUEUED']
        for status in working_statuses:
            orders_response = client.get_option_orders(account_id=account_hash, status=status, max_results=50)
            if orders_response.get('success'):
                for order in orders_response.get('data', []):
                    if str(order.get('orderId')) == str(original_order_id):
                        continue
                    for leg in order.get('orderLegCollection', []):
                        if leg.get('instrument', {}).get('assetType') == 'OPTION':
                            candidate_details = parse_option_symbol(leg.get('instrument', {}).get('symbol'))
                            if not candidate_details: continue
                            if (candidate_details['underlying'] == original_order['symbol'] and
                                candidate_details['put_call'] == original_order['option_type'] and
                                leg.get('instruction') == original_order['side'] and
                                abs(candidate_details['strike'] - original_order['strike_price']) < 0.001 and
                                candidate_details['expiry_date'] == original_order['expiration_date']):
                                app.logger.info(f"Found replacement order: {order.get('orderId')}")
                                return order
    app.logger.warning("No replacement order found after multiple attempts.")
    return None

def get_nearest_strike(price):
    if price < 10: return round(price * 2) / 2
    elif price < 50: return round(price)
    elif price < 100: return round(price / 2.5) * 2.5
    else: return round(price / 5) * 5

def get_next_friday():
    today = datetime.now()
    days_until_friday = (4 - today.weekday() + 7) % 7
    if days_until_friday == 0: days_until_friday = 7
    return (today + timedelta(days=days_until_friday)).strftime('%Y-%m-%d')

def parse_option_position_details(position: dict) -> dict or None:
    try:
        if position.get('assetType') != 'OPTION': return None
        description = position.get('description', '')
        desc_parts = description.split(' ')
        desc_expiry = datetime.strptime(desc_parts[-3], '%m/%d/%Y').strftime('%Y-%m-%d')
        desc_strike = float(desc_parts[-2].replace('$', ''))
        quantity = position.get('longQuantity', 0) - position.get('shortQuantity', 0)
        return {
            "put_call": position.get('putCall'),
            "strike": desc_strike,
            "expiry": desc_expiry,
            "quantity": quantity,
            "price": position.get('averagePrice')
        }
    except (ValueError, IndexError, TypeError):
        return None

# --- State Management ---
active_trade = {"order_id": None, "status": "Idle", "details": {}}

# --- Flask Routes ---
@app.route('/')
def index():
    return render_template('index.html')

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    with SchwabClient() as client:
        accounts = client.get_linked_accounts()
        if accounts and accounts.get('success'):
            account_list = accounts.get('data', [])
            if account_list:
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

@app.route('/api/positions/<symbol>', methods=['GET'])
def get_positions(symbol):
    account_hash = request.args.get('account_hash')
    if not account_hash: return jsonify({"success": False, "error": "Account hash required."}), 400
    with SchwabClient() as client:
        positions_response = client.get_positions_by_symbol(symbol=symbol.upper(), account_hash=account_hash)
        if positions_response.get('success') and positions_response.get('data'):
            position_strings = []
            accounts = positions_response.get('data', {}).get('accounts', [])
            for acc in accounts:
                for pos in acc.get('positions', []):
                    qty = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
                    if qty == 0: continue
                    if pos.get('assetType') == 'EQUITY':
                        position_strings.append(f"STOCK: {int(qty)}")
                    elif pos.get('assetType') == 'OPTION':
                        details = parse_option_position_details(pos)
                        if details:
                            price_str = f" @{details.get('price'):.2f}" if details.get('price') is not None else ""
                            position_strings.append(f"{details['quantity']:+g} {details['put_call']} Strk:{details['strike']}{price_str}")
            if not position_strings: return jsonify({"success": True, "display_text": "No Pos"})
            return jsonify({"success": True, "display_text": " | ".join(position_strings)})
    return jsonify({"success": False, "error": f"Could not retrieve positions for {symbol}."}), 500

@app.route('/api/recent_fills', methods=['GET'])
def get_recent_fills():
    account_hash = request.args.get('account_hash')
    if not account_hash: return jsonify({"success": False, "error": "Account hash required."}), 400
    with SchwabClient() as client:
        # Fetch today's filled orders
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
    call_qty, put_qty = 0, 0
    with SchwabClient() as client:
        positions_response = client.get_positions_by_symbol(symbol=symbol.upper(), account_hash=account_hash)
        if positions_response.get('success') and positions_response.get('data'):
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
    return jsonify({"success": False, "error": "Could not get positions."}), 500

@app.route('/api/order', methods=['POST'])
def handle_order():
    global active_trade
    data = request.json
    order_action = data.get('action')
    with SchwabClient() as client:
        if order_action == 'place':
            details = data['order_details']
            response = client.place_option_order(**details)
            if response.get('success'):
                order_id = response.get('data', {}).get('order_id')
                active_trade.update(order_id=order_id, status='WORKING', details=details)
                return jsonify({"success": True, "order_id": order_id})
            return jsonify({"success": False, "error": response.get('error')}), 500
        elif order_action == 'cancel':
            if active_trade.get('order_id'):
                response = client.cancel_option_order(account_id=active_trade['details']['account_id'], order_id=active_trade['order_id'])
                if response.get('success'):
                    active_trade.update(order_id=None, status='CANCELED', details={})
                    return jsonify({"success": True})
            return jsonify({"success": False, "error": "No active order"}), 400
    return jsonify({"success": False, "error": "Invalid action"}), 400

@app.route('/api/order_status', methods=['GET'])
def get_order_status():
    global active_trade
    if not active_trade.get('order_id'):
        return jsonify({"success": True, "data": {"status": "Idle"}})
    with SchwabClient() as client:
        response = client.get_option_order_details(account_id=active_trade['details']['account_id'], order_id=active_trade['order_id'])
        if response.get('success'):
            active_trade['status'] = response.get('data', {}).get('status')
            return jsonify({"success": True, "data": response.get('data', {})})
    return jsonify({"success": False, "error": "Could not get status."}), 404

@app.route('/api/find_replacement_order', methods=['POST'])
def find_replacement_order_api():
    data = request.get_json()
    if not data: return jsonify({"success": False, "error": "Invalid JSON"}), 400
    original_order = data.get('original_order')
    account_hash = data.get('account_hash')
    if not original_order or not account_hash:
        return jsonify({"success": False, "error": "Missing params"}), 400
    with SchwabClient() as client:
        replacement = find_replacement_order(client, account_hash, original_order)
        if replacement:
            return jsonify({"success": True, "replacement_order": replacement})
    return jsonify({"success": False, "error": "Not found"}), 404

if __name__ == '__main__':
    app.run(port=5001, debug=True)
