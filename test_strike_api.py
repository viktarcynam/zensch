import json
from datetime import date, timedelta
from client import SchwabClient

def run_test():
    """
    Uses the project's SchwabClient to connect to the API server and fetch
    an option chain using the strikeCount parameter.
    """
    print("Initializing SchwabClient to connect to the running server...")

    # The SchwabClient should be used as a context manager
    with SchwabClient() as client:
        # Define parameters for the API call
        symbol = 'SPY'
        strike_count = 12

        # Set an expiration date ~45 days in the future
        expiration_date = date.today() + timedelta(days=45)
        expiration_date_str = expiration_date.strftime('%Y-%m-%d')

        print("-" * 40)
        print(f"Testing with symbol:          {symbol}")
        print(f"Requesting strike count:      {strike_count}")
        print(f"Using target expiration date: {expiration_date_str}")
        print("-" * 40)

        try:
            # Call the get_option_chains method on the SchwabClient instance.
            # Note the kwargs use camelCase as expected by the client/server.
            response = client.get_option_chains(
                symbol=symbol,
                contractType='CALL',
                strikeCount=strike_count,
                toDate=expiration_date_str,
                fromDate=expiration_date_str,
            )

            print("Client request sent successfully.")

            # The client returns a dictionary. We first check for client-level success.
            if not response.get('success'):
                print(f"\nClient communication failed: {response.get('error')}")
                return

            # If client communication succeeded, we parse the nested data from the server.
            data = response.get('data', {})
            print(f"Server returned status: '{data.get('status')}'")

            if data.get('status') == 'SUCCESS':
                print(f"Underlying price: {data.get('underlyingPrice')}")

                exp_date_map = data.get('callExpDateMap', {})
                if not exp_date_map:
                    print("\nNo call options found for the specified expiration date.")
                    return

                # Get the actual expiration date returned by the API
                actual_expiration = next(iter(exp_date_map))
                strike_map = exp_date_map[actual_expiration]
                strikes = list(strike_map.keys())

                print(f"\nFound {len(strikes)} strikes for actual expiration {actual_expiration}:")
                sorted_strikes = sorted([float(s) for s in strikes])
                print(sorted_strikes)

                if len(sorted_strikes) > 0:
                    print(f"\nAnalysis:")
                    print(f"  Min strike:    {min(sorted_strikes)}")
                    print(f"  Max strike:    {max(sorted_strikes)}")
            else:
                print("\nServer indicated failure. Full server response:")
                print(json.dumps(data, indent=2))

        except Exception as e:
            print(f"\nAn unexpected error occurred during the client call: {e}")
            import traceback
            traceback.print_exc()


if __name__ == '__main__':
    run_test()
