import json
import time
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
        account_list = accounts.get('data', [])
        if account_list:
            return account_list[0].get('hashValue')
    print("Error: Could not retrieve account hash.")
    return None

def get_all_position_symbols(client, account_hash):
    """Get a unique set of symbols from all positions."""
    positions_response = client.get_positions(account_hash=account_hash)
    symbols = set()

    if positions_response.get('success') and positions_response.get('data'):
        data = positions_response.get('data', {})
        accounts = data.get('accounts', [])
        for acc in accounts:
            for pos in acc.get('positions', []):
                asset_type = pos.get('instrument', {}).get('assetType')
                if asset_type in ['EQUITY', 'OPTION']:
                    symbol = pos.get('instrument', {}).get('underlyingSymbol') or pos.get('instrument', {}).get('symbol')
                    if symbol:
                        symbols.add(symbol)
    return list(symbols)

def get_symbols_with_working_orders(client, account_hash):
    """Get a list of symbols that have working or pending activation orders."""
    symbols = set()
    working_statuses = ['WORKING', 'PENDING_ACTIVATION']

    for status in working_statuses:
        # Get stock orders
        stock_orders_response = client.get_stock_orders(account_id=account_hash, status=status)
        if stock_orders_response.get('success') and stock_orders_response.get('data'):
            for order in stock_orders_response.get('data', []):
                for leg in order.get('orderLegCollection', []):
                    symbol = leg.get('instrument', {}).get('symbol')
                    if symbol:
                        symbols.add(symbol)

        # Get option orders
        option_orders_response = client.get_option_orders(account_id=account_hash, status=status)
        if option_orders_response.get('success') and option_orders_response.get('data'):
            for order in option_orders_response.get('data', []):
                for leg in order.get('orderLegCollection', []):
                    instrument = leg.get('instrument', {})
                    if instrument.get('assetType') == 'OPTION':
                        symbol = instrument.get('underlyingSymbol')
                        if symbol:
                            symbols.add(symbol)
    return list(symbols)

def cancel_orders_for_symbol(client, account_hash, symbol):
    """Cancel all working or pending activation orders for a given symbol."""
    print(f"\nAttempting to cancel all working/pending orders for {symbol}...")
    working_statuses = ['WORKING', 'PENDING_ACTIVATION']

    for status in working_statuses:
        # Cancel stock orders
        stock_orders_response = client.get_stock_orders(account_id=account_hash, status=status)
        if stock_orders_response.get('success') and stock_orders_response.get('data'):
            for order in stock_orders_response.get('data', []):
                for leg in order.get('orderLegCollection', []):
                    if leg.get('instrument', {}).get('symbol') == symbol:
                        order_id = order.get('orderId')
                        print(f"Cancelling STOCK order ID: {order_id}")
                        cancel_response = client.cancel_stock_order(account_id=account_hash, order_id=order_id)
                        print_response(f"Cancel STOCK Order {order_id} Result", cancel_response)

        # Cancel option orders
        option_orders_response = client.get_option_orders(account_id=account_hash, status=status)
        if option_orders_response.get('success') and option_orders_response.get('data'):
            for order in option_orders_response.get('data', []):
                for leg in order.get('orderLegCollection', []):
                    instrument = leg.get('instrument', {})
                    if instrument.get('assetType') == 'OPTION' and instrument.get('underlyingSymbol') == symbol:
                        order_id = order.get('orderId')
                        print(f"Cancelling OPTION order ID: {order_id}")
                        cancel_response = client.cancel_option_order(account_id=account_hash, order_id=order_id)
                        print_response(f"Cancel OPTION Order {order_id} Result", cancel_response)


def main():
    """Main function for the interactive flatten client."""
    print("Schwab Interactive Flatten Client")
    print("Make sure the server is running before executing this script!")

    with SchwabClient() as client:
        account_hash = get_account_hash(client)
        if not account_hash:
            return

        print(f"Using account hash: {account_hash}")

        while True:
            try:
                # Display all position symbols
                all_symbols = get_all_position_symbols(client, account_hash)
                if all_symbols:
                    print("\n--- Symbols in Account ---")
                    print(", ".join(sorted(all_symbols)))
                else:
                    print("\nNo positions found in the account.")

                # Display symbols with working orders
                symbols_with_orders = get_symbols_with_working_orders(client, account_hash)

                print("\n" + "="*40)

                if not symbols_with_orders:
                    print("No symbols with working or pending activation orders found.")
                    break

                print("Symbols with Active Orders to Flatten:")
                for i, symbol in enumerate(symbols_with_orders, 1):
                    print(f"{i}. {symbol}")

                print("="*40)

                # Prompt for user input
                choice = input("Enter the number of the symbol to flatten (or 'quit' to exit): ").strip()

                if choice.lower() == 'quit':
                    break

                if not choice.isdigit():
                    print("Invalid input. Please enter a number.")
                    continue

                choice_idx = int(choice) - 1

                if 0 <= choice_idx < len(symbols_with_orders):
                    symbol_to_flatten = symbols_with_orders[choice_idx]
                    confirm = input(f"Are you sure you want to cancel all working orders for {symbol_to_flatten}? (yes/no): ").lower()
                    if confirm == 'yes':
                        cancel_orders_for_symbol(client, account_hash, symbol_to_flatten)
                        print(f"\nFlatten process completed for {symbol_to_flatten}. Please verify the status of your orders.")
                        time.sleep(3) # Give user time to read the output
                    else:
                        print("Flatten operation cancelled.")
                else:
                    print("Invalid number. Please choose a number from the list.")

            except KeyboardInterrupt:
                print("\nClient interrupted by user.")
                break
            except Exception as e:
                print(f"\nAn error occurred: {e}")
                continue

    print("\nClient disconnected.")

if __name__ == "__main__":
    main()
