import json
import schwabdev
from datetime import datetime, timedelta
from config import config

def main():
    """Main function to debug orders by calling schwabdev directly."""
    print("--- Direct Schwab API Order Debugger ---")

    # --- Get Credentials from existing config ---
    if not config.is_configured():
        print("\nAPI credentials are not configured.")
        print("Please set SCHWAB_APP_KEY and SCHWAB_APP_SECRET environment variables,")
        print("or configure them in creds.yml.")
        return

    # --- Authenticate ---
    try:
        print("\nAttempting to authenticate using existing configuration...")
        client = schwabdev.Client(config.app_key, config.app_secret, config.callback_url, config.tokens_file)
        # The schwabdev client will handle token refresh automatically.
        # A full re-authentication (browser flow) will only happen if tokens are invalid or expired.
        print("Authentication check complete (used existing tokens if available).")
    except Exception as e:
        print(f"\nAuthentication failed: {e}")
        return

    # --- Get Account Hash ---
    try:
        print("\nFetching account hash...")
        accounts_response = client.account_linked()
        if not accounts_response.ok:
            print(f"Failed to get accounts: {accounts_response.text}")
            return

        accounts = accounts_response.json()
        if not accounts:
            print("No accounts found.")
            return

        account_hash = accounts[0].get('hashValue')
        print(f"Using account hash: {account_hash}")
    except Exception as e:
        print(f"Error getting account hash: {e}")
        return

    # --- API Call 1: Max Results ---
    try:
        print("\n--- Making API Call 1: 10 Most Recent Orders ---")
        to_time_mr = datetime.now()
        from_time_mr = to_time_mr - timedelta(days=90) # Use a wide window for recency

        orders_max_results = client.account_orders(
            account_hash,
            fromEnteredTime=from_time_mr,
            toEnteredTime=to_time_mr,
            maxResults=10
        )

        print("\n--- Summary (max_results=10) ---")
        if orders_max_results.ok:
            orders = orders_max_results.json()
            if orders:
                for order in orders:
                    print(f"  - Order ID: {order.get('orderId')}, Status: {order.get('status')}")
            else:
                print("  No orders found.")
            print("\n--- Raw Response (max_results=10) ---")
            print(json.dumps(orders, indent=2))
        else:
            print(f"Error: {orders_max_results.status_code} - {orders_max_results.text}")

    except Exception as e:
        print(f"\nAn error occurred during API Call 1: {e}")

    # --- API Call 2: Time Window ---
    try:
        print("\n--- Making API Call 2: Last 24 Hours ---")
        to_time_tw = datetime.now()
        from_time_tw = to_time_tw - timedelta(hours=24)

        orders_time_window = client.account_orders(
            account_hash,
            fromEnteredTime=from_time_tw,
            toEnteredTime=to_time_tw
        )

        print("\n--- Summary (last 24 hours) ---")
        if orders_time_window.ok:
            orders = orders_time_window.json()
            if orders:
                for order in orders:
                    print(f"  - Order ID: {order.get('orderId')}, Status: {order.get('status')}")
            else:
                print("  No orders found.")
            print("\n--- Raw Response (last 24 hours) ---")
            print(json.dumps(orders, indent=2))
        else:
            print(f"Error: {orders_time_window.status_code} - {orders_time_window.text}")

    except Exception as e:
        print(f"\nAn error occurred during API Call 2: {e}")

    # --- API Call 3: Get Order by ID ---
    try:
        print("\n--- Making API Call 3: Get Order by ID ---")
        order_id_to_check = input("Enter an Order ID to get details (or press Enter to skip): ").strip()

        if order_id_to_check:
            order_details = client.order_details(account_hash, order_id_to_check)

            print(f"\n--- Raw Response (Order ID: {order_id_to_check}) ---")
            if order_details.ok:
                print(json.dumps(order_details.json(), indent=2))
            else:
                print(f"Error: {order_details.status_code} - {order_details.text}")
        else:
            print("Skipping API Call 3.")

    except Exception as e:
        print(f"\nAn error occurred during API Call 3: {e}")


if __name__ == "__main__":
    main()
