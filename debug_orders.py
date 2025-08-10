import json
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
    """Main function to debug option orders."""
    print("--- Option Order Debugger ---")

    with SchwabClient() as client:
        account_hash = get_account_hash(client)
        if not account_hash:
            return

        print(f"Using account hash: {account_hash}")

        # Fetch all recent option orders without a status filter
        orders_response = client.get_option_orders(account_id=account_hash)

        if orders_response.get('success'):
            print("\n--- Raw Order Data ---")
            print(json.dumps(orders_response.get('data', []), indent=2))
        else:
            print("\n--- Error ---")
            print(json.dumps(orders_response, indent=2))

if __name__ == "__main__":
    main()
