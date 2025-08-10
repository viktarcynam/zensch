import json
from datetime import datetime, timedelta
from client import SchwabClient

def get_account_hash(client):
    """Get the first account hash."""
    accounts = client.get_linked_accounts()
    if accounts and accounts.get('success'):
        account_list = accounts.get('data', [])
        if account_list:
            return account_list[0].get('hashValue')
    print("Error: Could not retrieve account hash.")
    return None

def main():
    """Main function to debug option orders by time."""
    print("--- Option Order Debugger (Time Filter) ---")

    with SchwabClient() as client:
        account_hash = get_account_hash(client)
        if not account_hash:
            return

        print(f"Using account hash: {account_hash}")

        # Calculate time window
        to_time = datetime.now()
        from_time = to_time - timedelta(hours=12)

        print(f"Fetching orders from {from_time.isoformat()} to {to_time.isoformat()}")

        # Fetch option orders within the time window
        orders_response = client.get_option_orders(
            account_id=account_hash,
            from_entered_time=from_time.isoformat(),
            to_entered_time=to_time.isoformat()
        )

        if orders_response.get('success'):
            print("\n--- Raw Order Data (Last 12 Hours) ---")
            print(json.dumps(orders_response.get('data', []), indent=2))
        else:
            print("\n--- Error ---")
            print(json.dumps(orders_response, indent=2))

if __name__ == "__main__":
    main()
