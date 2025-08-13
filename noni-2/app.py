from flask import Flask, jsonify, request, render_template
import sys
import os
import uuid
from datetime import datetime, timedelta

# Add the parent directory to the Python path to import the client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client import SchwabClient

app = Flask(__name__)

# --- Helper functions from noni-1.py ---

def get_nearest_strike(price):
    """Find the nearest strike price."""
    if price < 10:
        return round(price * 2) / 2
    elif price < 50:
        return round(price)
    elif price < 100:
        return round(price / 2.5) * 2.5
    else:
        return round(price / 5) * 5

def get_next_friday():
    """Get the next upcoming Friday's date."""
    today = datetime.now()
    days_until_friday = (4 - today.weekday() + 7) % 7
    if days_until_friday == 0:
        days_until_friday = 7
    next_friday = today + timedelta(days=days_until_friday)
    return next_friday.strftime('%Y-%m-%d')

def parse_option_position_details(position: dict) -> dict or None:
    """
    Parses an option position object to extract key details.
    """
    try:
        if position.get('assetType') != 'OPTION':
            return None
        description = position.get('description', '')
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
            "quantity": quantity,
            "price": position.get('price') # Add trade price
        }
    except (ValueError, IndexError, TypeError):
        return None

# --- State Management ---
active_trade = {
    "order_id": None,
    "status": "Idle",
    "details": {}
}

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
            quote_string = quotes_response['data'][0]
            parts = quote_string.split()
            try:
                last_price = float(parts[1])
                suggested_strike = get_nearest_strike(last_price)
                suggested_expiry = get_next_friday()
                return jsonify({
                    "success": True,
                    "strike": suggested_strike,
                    "expiry": suggested_expiry,
                    "price": last_price
                })
            except (ValueError, IndexError):
                 return jsonify({"success": False, "error": "Could not parse last price."}), 500
    return jsonify({"success": False, "error": f"Could not retrieve quote for {symbol}."}), 404

@app.route('/api/underlying_price/<symbol>', methods=['GET'])
def get_underlying_price(symbol):
    with SchwabClient() as client:
        quotes_response = client.get_quotes(symbols=[symbol.upper()])
        if quotes_response.get('success') and quotes_response.get('data'):
            quote_string = quotes_response['data'][0]
            parts = quote_string.split()
            try:
                last_price = float(parts[1])
                return jsonify({"success": True, "price": last_price})
            except (ValueError, IndexError):
                 return jsonify({"success": False, "error": "Could not parse price."}), 500
    return jsonify({"success": False, "error": "Could not retrieve quote."}), 404

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
                            qty_str = f"+{int(details['quantity'])}" if details['quantity'] > 0 else str(int(details['quantity']))
                            price_str = f" @{details.get('price', 'N/A')}"
                            position_strings.append(f"{qty_str} {details['put_call']} Strk:{details['strike']}{price_str}")
                        else:
                            position_strings.append(f"{int(qty)} of {pos.get('description', 'Unknown Option')}")
            if not position_strings: return jsonify({"success": True, "display_text": "No Pos"})
            return jsonify({"success": True, "display_text": " | ".join(position_strings)})
    return jsonify({"success": False, "error": f"Could not retrieve positions for {symbol}."}), 500

@app.route('/api/recent_fills', methods=['GET'])
def get_recent_fills():
    account_hash = request.args.get('account_hash')
    if not account_hash: return jsonify({"success": False, "error": "Account hash required."}), 400
    with SchwabClient() as client:
        orders_response = client.get_option_orders(account_id=account_hash, status='FILLED', max_results=5)
        if orders_response.get('success') and orders_response.get('data'):
            fills_strings = []
            for order in orders_response.get('data', []):
                try:
                    leg = order['orderLegCollection'][0]
                    instrument = leg['instrument']
                    activity = order['orderActivityCollection'][0]['executionLegs'][0]
                    qty = leg['quantity']
                    side = leg['instruction']
                    if 'BUY' in side:
                        qty_str = f"+{int(qty)}"
                    else:
                        qty_str = f"-{int(qty)}"

                    symbol = instrument['underlyingSymbol']
                    put_call = instrument['putCall'][0] # P or C
                    price = activity['price']

                    fills_strings.append(f"{qty_str}{put_call} {symbol} {price:.2f}")
                except (IndexError, KeyError) as e:
                    print(f"Error parsing filled order: {e}")
                    continue
            return jsonify({"success": True, "fills": fills_strings})
    return jsonify({"success": False, "error": "Could not retrieve recent fills."}), 500


@app.route('/api/options/<symbol>/<strike>/<expiry>', methods=['GET'])
def get_options(symbol, strike, expiry):
    with SchwabClient() as client:
        option_chain_response = client.get_option_chains(symbol=symbol.upper(), strike=float(strike), fromDate=expiry, toDate=expiry, contractType='ALL')
        if option_chain_response.get('success'):
            return jsonify({"success": True, "data": option_chain_response.get('data', {})})
    return jsonify({"success": False, "error": "Could not retrieve option chain."}), 500

@app.route('/api/instrument_position', methods=['GET'])
def get_instrument_position():
    account_hash = request.args.get('account_hash')
    symbol = request.args.get('symbol')
    strike = float(request.args.get('strike'))
    expiry = request.args.get('expiry')
    option_type = request.args.get('option_type')
    if not all([account_hash, symbol, strike, expiry, option_type]):
        return jsonify({"success": False, "error": "Missing params for instrument position."}), 400
    with SchwabClient() as client:
        positions_response = client.get_positions_by_symbol(symbol=symbol.upper(), account_hash=account_hash)
        if positions_response.get('success') and positions_response.get('data'):
            accounts = positions_response.get('data', {}).get('accounts', [])
            for acc in accounts:
                for pos in acc.get('positions', []):
                    details = parse_option_position_details(pos)
                    if details:
                        if (details['put_call'] == option_type and abs(details['strike'] - strike) < 0.001 and details['expiry'] == expiry):
                            return jsonify({"success": True, "quantity": details['quantity']})
            return jsonify({"success": True, "quantity": 0})
    return jsonify({"success": False, "error": f"Could not retrieve positions for {symbol}."}), 500

@app.route('/api/order', methods=['POST'])
def handle_order():
    global active_trade
    data = request.json
    order_action = data.get('action')
    with SchwabClient() as client:
        if order_action == 'place_or_replace':
            new_order_details = data['order_details']
            current_quantity = 0
            pos_response = client.get_positions_by_symbol(symbol=new_order_details['symbol'], account_hash=new_order_details['account_id'])
            if pos_response.get('success') and pos_response.get('data'):
                accounts = pos_response.get('data', {}).get('accounts', [])
                for acc in accounts:
                    for pos in acc.get('positions', []):
                        details = parse_option_position_details(pos)
                        if details:
                            if (details['put_call'] == new_order_details['option_type'] and abs(details['strike'] - new_order_details['strike_price']) < 0.001 and details['expiry'] == new_order_details['expiration_date']):
                                current_quantity = details['quantity']
                                break
                    if current_quantity != 0: break

            action = new_order_details.pop('simple_action')
            if action == 'B':
                new_order_details['side'] = 'BUY_TO_CLOSE' if current_quantity < 0 else 'BUY_TO_OPEN'
            else: # 'S'
                new_order_details['side'] = 'SELL_TO_CLOSE' if current_quantity > 0 else 'SELL_TO_OPEN'

            if not active_trade.get('order_id') or active_trade.get('status') not in ['WORKING', 'PENDING_ACTIVATION']:
                response = client.place_option_order(**new_order_details)
                if response.get('success'):
                    order_id = response.get('data', {}).get('order_id')
                    active_trade.update(order_id=order_id, status='WORKING', details=new_order_details)
                    return jsonify({"success": True, "message": "Order placed.", "order_id": order_id, "trade_status": new_order_details['side']})
                else:
                    return jsonify({"success": False, "error": response.get('error', 'Failed to place order')}), 500
            else:
                current_details = active_trade['details']
                cancel_response = client.cancel_option_order(account_id=current_details['account_id'], order_id=active_trade['order_id'])
                if not cancel_response.get('success'):
                    return jsonify({"success": False, "error": f"Failed to cancel previous order: {cancel_response.get('error')}"}), 500

                place_response = client.place_option_order(**new_order_details)
                if place_response.get('success'):
                    order_id = place_response.get('data', {}).get('order_id')
                    active_trade.update(order_id=order_id, status='WORKING', details=new_order_details)
                    return jsonify({"success": True, "message": "Previous order canceled, new order placed.", "order_id": order_id, "trade_status": new_order_details['side']})
                else:
                    return jsonify({"success": False, "error": f"Canceled previous order but failed to place new one: {place_response.get('error')}"}), 500

        elif order_action == 'cancel':
            if active_trade.get('order_id'):
                response = client.cancel_option_order(account_id=active_trade['details']['account_id'], order_id=active_trade['order_id'])
                if response.get('success'):
                    active_trade.update(order_id=None, status='CANCELED', details={})
                    return jsonify({"success": True, "message": "Order canceled."})
                else:
                    return jsonify({"success": False, "error": response.get('error', 'Failed to cancel order')}), 500
            else:
                return jsonify({"success": False, "error": "No active order to cancel."}), 400

        else:
            return jsonify({"success": False, "error": "Invalid order action"}), 400

@app.route('/api/order_status', methods=['GET'])
def get_order_status():
    global active_trade
    if not active_trade.get('order_id'):
        return jsonify({"success": True, "data": {"status": "Idle"}})
    account_hash = active_trade['details'].get('account_id')
    order_id = active_trade.get('order_id')
    if not account_hash or not order_id:
         return jsonify({"success": False, "error": "Missing account hash or order ID."}), 500
    with SchwabClient() as client:
        order_details_response = client.get_option_order_details(account_id=account_hash, order_id=order_id)
        if order_details_response.get('success'):
            new_status = order_details_response.get('data', {}).get('status')
            active_trade['status'] = new_status
            return jsonify({"success": True, "data": order_details_response.get('data', {})})
    return jsonify({"success": False, "error": f"Could not retrieve status for order {order_id}."}), 404

if __name__ == '__main__':
    app.run(port=5001, debug=True)
