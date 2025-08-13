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
    if days_until_friday == 0: # If today is Friday, get next Friday
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


# --- State Management ---
# Simplified for a single active trade model based on new UI
active_trade = {
    "order_id": None,
    "status": "Idle",
    "details": {},
    "instrument_position": 0, # e.g., +1, -1, 0
    "trade_side": None # e.g., 'long' or 'short'
}

@app.route('/')
def index():
    """Serves the main HTML page."""
    return render_template('index.html')

@app.route('/api/accounts', methods=['GET'])
def get_accounts():
    """Get the Schwab account hash."""
    with SchwabClient() as client:
        accounts = client.get_linked_accounts()
        if accounts and accounts.get('success'):
            account_list = accounts.get('data', [])
            if account_list:
                return jsonify({"success": True, "account_hash": account_list[0].get('hashValue')})
    return jsonify({"success": False, "error": "Could not retrieve account hash."}), 500

@app.route('/api/defaults/<symbol>', methods=['GET'])
def get_defaults(symbol):
    """Get default strike and expiry for a symbol."""
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
                    "expiry": suggested_expiry
                })
            except (ValueError, IndexError):
                 return jsonify({"success": False, "error": "Could not parse last price from quote."}), 500
    return jsonify({"success": False, "error": f"Could not retrieve quote for {symbol}."}), 404


@app.route('/api/positions/<symbol>', methods=['GET'])
def get_positions(symbol):
    """Get positions for a given symbol."""
    account_hash = request.args.get('account_hash')
    if not account_hash:
        return jsonify({"success": False, "error": "Account hash is required."}), 400

    with SchwabClient() as client:
        positions_response = client.get_positions_by_symbol(symbol=symbol.upper(), account_hash=account_hash)
        if positions_response.get('success') and positions_response.get('data'):
            position_strings = []
            accounts = positions_response.get('data', {}).get('accounts', [])
            for acc in accounts:
                for pos in acc.get('positions', []):
                    qty = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
                    if qty == 0:
                        continue

                    if pos.get('assetType') == 'EQUITY':
                        position_strings.append(f"STOCK: {int(qty)}")
                    elif pos.get('assetType') == 'OPTION':
                        details = parse_option_position_details(pos)
                        if details:
                            qty_str = f"+{int(details['quantity'])}" if details['quantity'] > 0 else str(int(details['quantity']))
                            position_strings.append(f"{qty_str} {details['put_call']} Strk:{details['strike']} Exp:{details['expiry']}")
                        else:
                            position_strings.append(f"{int(qty)} of {pos.get('description', 'Unknown Option')}")

            if not position_strings:
                return jsonify({"success": True, "display_text": "No Pos"})

            return jsonify({"success": True, "display_text": " | ".join(position_strings)})

    return jsonify({"success": False, "error": f"Could not retrieve positions for {symbol}."}), 500

@app.route('/api/options/<symbol>/<strike>/<expiry>', methods=['GET'])
def get_options(symbol, strike, expiry):
    """Get the option chain for a specific option."""
    with SchwabClient() as client:
        option_chain_response = client.get_option_chains(
            symbol=symbol.upper(),
            strike=float(strike),
            fromDate=expiry,
            toDate=expiry,
            contractType='ALL'
        )
        if option_chain_response.get('success'):
            return jsonify({"success": True, "data": option_chain_response.get('data', {})})
    return jsonify({"success": False, "error": "Could not retrieve option chain."}), 500

@app.route('/api/order', methods=['POST'])
def handle_order():
    """A POST endpoint to place, modify, or cancel an order."""
    global active_trade
    data = request.json
    order_action = data.get('action') # 'place_or_replace', 'cancel'

    with SchwabClient() as client:
        if order_action == 'place_or_replace':
            new_order_details = data['order_details']

            # Backend determines the correct 'side'
            action = new_order_details.pop('simple_action') # 'B' or 'S'

            if action == 'B':
                new_order_details['side'] = 'BUY_TO_CLOSE' if active_trade.get('trade_side') == 'short' else 'BUY_TO_OPEN'
            else: # 'S'
                new_order_details['side'] = 'SELL_TO_CLOSE' if active_trade.get('trade_side') == 'long' else 'SELL_TO_OPEN'

            # If there's no active order, just place it.
            if not active_trade.get('order_id') or active_trade.get('status') not in ['WORKING', 'PENDING_ACTIVATION']:
                response = client.place_option_order(**new_order_details)
                if response.get('success'):
                    order_id = response.get('data', {}).get('order_id')
                    active_trade.update(order_id=order_id, status='WORKING', details=new_order_details, instrument_position=0)
                    return jsonify({"success": True, "message": "Order placed.", "order_id": order_id, "trade_status": new_order_details['side']})
                else:
                    return jsonify({"success": False, "error": response.get('error', 'Failed to place order')}), 500

            # If there is an active order, cancel the old and place the new.
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
    """Get the status of the active order and update instrument position on fill."""
    global active_trade
    if not active_trade.get('order_id'):
        return jsonify({"success": True, "data": {"status": "Idle", "instrument_position": 0}})

    account_hash = active_trade['details'].get('account_id')
    order_id = active_trade.get('order_id')

    if not account_hash or not order_id:
         return jsonify({"success": False, "error": "Missing account hash or order ID in active trade."}), 500

    with SchwabClient() as client:
        order_details_response = client.get_option_order_details(account_id=account_hash, order_id=order_id)

        if order_details_response.get('success'):
            new_status = order_details_response.get('data', {}).get('status')

            # Check if the order was just filled
            if new_status == 'FILLED' and active_trade['status'] != 'FILLED':
                instruction = active_trade['details'].get('side', '')
                quantity = active_trade['details'].get('quantity', 0)

                if 'BUY' in instruction:
                    active_trade['instrument_position'] += quantity
                    active_trade['trade_side'] = 'long'
                elif 'SELL' in instruction:
                    active_trade['instrument_position'] -= quantity
                    if active_trade['instrument_position'] == 0:
                        active_trade['trade_side'] = None # Closed the position

            # Update server-side status
            active_trade['status'] = new_status

            # Add instrument_position to the response
            response_data = order_details_response.get('data', {})
            response_data['instrument_position'] = active_trade['instrument_position']

            return jsonify({"success": True, "data": response_data})

    return jsonify({"success": False, "error": f"Could not retrieve status for order {order_id}."}), 404


if __name__ == '__main__':
    # Note: For development, it's often better to run Flask with `flask run`
    # after setting FLASK_APP and FLASK_ENV.
    # e.g., export FLASK_APP=noni-2/app.py; export FLASK_ENV=development; flask run
    app.run(port=5001, debug=True)
