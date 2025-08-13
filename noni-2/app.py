from flask import Flask, jsonify, request, render_template
import sys
import os

# Add the parent directory to the Python path to import the client
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from client import SchwabClient

app = Flask(__name__)

import uuid

# In-memory store for active trading sessions
# This will allow us to manage multiple noni-1 like instances
# The key will be a unique session ID, and the value will be the state
trading_sessions = {}

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

@app.route('/api/quote/<symbol>', methods=['GET'])
def get_quote(symbol):
    """Get a quote for a stock symbol."""
    with SchwabClient() as client:
        quotes_response = client.get_quotes(symbols=[symbol.upper()])
        if quotes_response.get('success') and quotes_response.get('data'):
            return jsonify({"success": True, "data": quotes_response['data'][0]})
    return jsonify({"success": False, "error": f"Could not retrieve quote for {symbol}."}), 404

@app.route('/api/positions/<symbol>', methods=['GET'])
def get_positions(symbol):
    """Get positions for a given symbol."""
    account_hash = request.args.get('account_hash')
    if not account_hash:
        return jsonify({"success": False, "error": "Account hash is required."}), 400

    with SchwabClient() as client:
        positions_response = client.get_positions_by_symbol(symbol=symbol.upper(), account_hash=account_hash)
        if positions_response.get('success'):
            return jsonify({"success": True, "data": positions_response.get('data', {})})
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
    data = request.json
    order_action = data.get('order_action') # 'place', 'cancel', 'replace'

    with SchwabClient() as client:
        if order_action == 'place':
            response = client.place_option_order(**data['order_details'])
            if response.get('success'):
                order_id = response.get('data', {}).get('order_id')
                session_id = str(uuid.uuid4())
                trading_sessions[session_id] = {'order_id': order_id, 'status': 'WORKING', 'details': data['order_details']}
                return jsonify({"success": True, "message": "Order placed.", "session_id": session_id, "order_id": order_id})
            else:
                return jsonify({"success": False, "error": response.get('error', 'Failed to place order')}), 500

        elif order_action == 'cancel':
            response = client.cancel_option_order(account_id=data['account_id'], order_id=data['order_id'])
            if response.get('success'):
                 # Update session status if tracking
                for session_id, session_data in trading_sessions.items():
                    if session_data['order_id'] == data['order_id']:
                        session_data['status'] = 'CANCELED'
                        break
                return jsonify({"success": True, "message": "Order canceled."})
            else:
                return jsonify({"success": False, "error": response.get('error', 'Failed to cancel order')}), 500

        elif order_action == 'replace':
            response = client.replace_option_order(**data['order_details'])
            if response.get('success'):
                new_order_id = response.get('data', {}).get('new_order_id')
                # Update session with new order_id
                for session_id, session_data in trading_sessions.items():
                    if session_data['order_id'] == data['order_details']['order_id']:
                        session_data['order_id'] = new_order_id
                        session_data['details'] = data['order_details']
                        break
                return jsonify({"success": True, "message": "Order replaced.", "new_order_id": new_order_id})
            else:
                 return jsonify({"success": False, "error": response.get('error', 'Failed to replace order')}), 500

        else:
            return jsonify({"success": False, "error": "Invalid order action"}), 400


@app.route('/api/order_status/<order_id>', methods=['GET'])
def get_order_status(order_id):
    """Get the status of a specific order."""
    # This endpoint will need the account hash
    account_hash = request.args.get('account_hash')
    if not account_hash:
        return jsonify({"success": False, "error": "Account hash is required."}), 400

    with SchwabClient() as client:
        order_details_response = client.get_option_order_details(account_id=account_hash, order_id=order_id)
        if order_details_response.get('success'):
            return jsonify({"success": True, "data": order_details_response.get('data', {})})
    return jsonify({"success": False, "error": f"Could not retrieve status for order {order_id}."}), 404


if __name__ == '__main__':
    # Note: For development, it's often better to run Flask with `flask run`
    # after setting FLASK_APP and FLASK_ENV.
    # e.g., export FLASK_APP=noni-2/app.py; export FLASK_ENV=development; flask run
    app.run(port=5001, debug=True)
