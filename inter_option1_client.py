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

def get_account_hash(client):
    """Get the first account hash."""
    accounts = client.get_linked_accounts()
    if accounts and accounts.get('success'):
        account_list = accounts.get('accounts', [])
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
                if not quotes_response.get('success') or not quotes_response.get('quotes'):
                    print(f"Could not retrieve quote for {symbol}.")
                    continue

                quote = quotes_response['quotes'].get(symbol)
                if not quote or 'lastPrice' not in quote.get('quote', {}):
                    print(f"Could not retrieve last price for {symbol}.")
                    continue

                last_price = quote['quote']['lastPrice']
                print(f"Last price for {symbol}: {last_price}")

                # Get suggested strike and expiry
                suggested_strike = get_nearest_strike(last_price)
                suggested_expiry = get_next_friday()

                strike_price_str = input(f"Enter strike price (default: {suggested_strike}): ")
                strike_price = float(strike_price_str) if strike_price_str else suggested_strike

                expiry_date_str = input(f"Enter option expiry date (YYYY-MM-DD, default: {suggested_expiry}): ")
                expiry_date = expiry_date_str if expiry_date_str else suggested_expiry

                # Get option chain
                option_chain_response = client.get_option_chains(
                    symbol=symbol,
                    strike=strike_price,
                    fromDate=expiry_date,
                    toDate=expiry_date,
                    contractType='ALL'
                )

                if not option_chain_response.get('success'):
                    print(f"Could not retrieve option chain: {option_chain_response.get('error')}")
                    continue

                call_map = option_chain_response.get('callExpDateMap', {})
                put_map = option_chain_response.get('putExpDateMap', {})

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

                print(f"CALL:   {call_data['bid']}/{call_data['ask']}  PUT: {put_data['bid']}/{put_data['ask']}")

                # Display positions
                positions_response = client.get_positions_by_symbol(symbol=symbol, account_hash=account_hash)
                if positions_response.get('success') and positions_response.get('positions'):
                    positions = positions_response.get('positions')
                    position_strings = []
                    for pos in positions:
                        qty = pos.get('longQuantity', 0) - pos.get('shortQuantity', 0)
                        desc = pos.get('instrument', {}).get('description', 'Unknown')
                        position_strings.append(f"{qty} of {desc}")
                    if position_strings:
                        print(f"Positions: {'; '.join(position_strings)}")
                else:
                    print("No positions for this symbol in this account.")

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

                price_too_far = False
                if action == 'B': # Buying
                    if market_ask > 0 and price > market_ask * 1.5:
                        price_too_far = True
                else: # Selling
                    if market_bid > 0 and price < market_bid * 0.5:
                        price_too_far = True

                if price_too_far:
                    print("Price difference too high and rejected.")
                    continue

                quantity_str = input("Enter quantity (default: 1): ")
                quantity = int(quantity_str) if quantity_str else 1

                # Place order
                side = ""
                if action == 'B':
                    side = "BUY_TO_OPEN"
                else: # 'S'
                    side = "SELL_TO_CLOSE" if any(p['instrument'].get('symbol') == target_option_data['symbol'] for p in positions_response.get('positions',[])) else "SELL_TO_OPEN"


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

            except KeyboardInterrupt:
                print("\nClient interrupted by user.")
                break
            except Exception as e:
                print(f"\nAn error occurred: {e}")
                continue

    print("\nClient disconnected.")

if __name__ == "__main__":
    main()
