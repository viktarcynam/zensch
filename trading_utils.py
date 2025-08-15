import time
from datetime import datetime, timedelta


def parse_option_symbol(symbol_string):
    """
    Parses a standard OCC option symbol string.
    Example: 'HOG   250815C00024000'
    Returns: A dictionary with 'underlying', 'expiry_date', 'put_call', 'strike'.
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
        # This function is used by both CLI and web, so direct printing is not ideal.
        # The caller should handle the None return value.
        return None


def get_nearest_strike(price):
    """Find the nearest strike price based on the underlying price."""
    if price < 10:
        return round(price * 2) / 2  # Nearest 0.5
    elif price < 50:
        return round(price)
    elif price < 100:
        return round(price / 2.5) * 2.5  # Nearest 2.5
    else:
        return round(price / 5) * 5  # Nearest 5


def get_next_friday():
    """Get the next upcoming Friday's date."""
    today = datetime.now()
    days_until_friday = (4 - today.weekday() + 7) % 7
    if days_until_friday == 0:  # If today is Friday, get next Friday
        days_until_friday = 7
    next_friday = today + timedelta(days=days_until_friday)
    return next_friday.strftime('%Y-%m-%d')


def parse_instrument_description(description: str) -> dict or None:
    """
    Parses an instrument description string to extract strike and expiry.
    Example: "NOVO-NORDISK A/S 08/22/2025 $150 Put"
    Returns a dictionary with 'strike' and 'expiry', or None on failure.
    """
    try:
        if not description:
            return None

        desc_parts = description.split(' ')
        # Assumes the format is "... <Date> <Strike> <Type>"
        desc_expiry_str = desc_parts[-3]
        desc_strike_str = desc_parts[-2].replace('$', '')

        expiry = datetime.strptime(desc_expiry_str, '%m/%d/%Y').strftime('%Y-%m-%d')
        strike = float(desc_strike_str)

        return {
            "strike": strike,
            "expiry": expiry
        }
    except (ValueError, IndexError, TypeError):
        return None


def parse_option_position_details(position: dict) -> dict or None:
    """
    Parses an option position object to extract key details.
    The description string is parsed for strike and expiry.
    Returns a dictionary with details, or None on failure.
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
        average_price = position.get('averagePrice', 0.0)

        return {
            "put_call": position.get('putCall'),
            "strike": desc_strike,
            "expiry": desc_expiry,
            "quantity": quantity,
            "price": average_price
        }
    except (ValueError, IndexError, TypeError):
        return None


def find_replacement_order(client, account_hash, original_order, logger=None):
    """
    Finds the new order that replaced an old one by searching working orders.

    :param client: The SchwabClient instance.
    :param account_hash: The account hash string.
    :param original_order: A dictionary with original order details.
                           Required keys: 'orderId', 'symbol', 'putCall',
                           'instruction', 'strike', 'expiry'.
    :param logger: Optional logger instance for logging messages.
    :return: The replacement order dictionary or None.
    """
    log = logger.info if logger else print

    original_order_id = original_order['orderId']
    log(f"Searching for replacement of order {original_order_id}...")

    max_retries = 3
    retry_delay = 2  # seconds

    for attempt in range(max_retries):
        if attempt > 0:
            log(f"Retrying search... (Attempt {attempt + 1}/{max_retries})")
            time.sleep(retry_delay)

        working_statuses = ['WORKING', 'PENDING_ACTIVATION', 'ACCEPTED', 'QUEUED']
        all_working_orders = []

        for status in working_statuses:
            orders_response = client.get_option_orders(account_id=account_hash, status=status, max_results=50)
            if orders_response.get('success'):
                all_working_orders.extend(orders_response.get('data', []))
            else:
                warn = logger.warning if logger else print
                warn(f"Warning: Could not retrieve orders with status '{status}'.")

        if not all_working_orders and attempt < max_retries - 1:
            continue

        for order in all_working_orders:
            if str(order.get('orderId')) == str(original_order_id):
                continue

            for leg in order.get('orderLegCollection', []):
                instrument = leg.get('instrument', {})
                if instrument.get('assetType') == 'OPTION':
                    candidate_details = parse_option_symbol(instrument.get('symbol'))
                    if not candidate_details:
                        continue

                    # Compare all key details. Price is expected to be different.
                    if (candidate_details['underlying'] == original_order['symbol'] and
                            candidate_details['put_call'] == original_order['putCall'] and
                            leg.get('instruction') == original_order['instruction'] and
                            abs(candidate_details['strike'] - original_order['strike']) < 0.001 and
                            candidate_details['expiry_date'] == original_order['expiry']):
                        log(f"Found replacement order: {order.get('orderId')} with status {order.get('status')}")
                        return order

    log("No replacement order found after multiple attempts.")
    return None
