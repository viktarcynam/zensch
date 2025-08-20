import schwabdev
import logging
import sys
from creds_manager import CredsManager

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

def main():
    """
    Main function to handle Schwab authentication.
    """
    logging.info("Starting Schwab authentication process...")
    creds_manager = CredsManager()

    # Check if creds.yml exists
    if not creds_manager.has_valid_credentials():
        logging.warning("creds.yml not found or is invalid.")
        try:
            creds_manager.create_sample_creds_file()
            logging.info("A sample 'creds.yml' has been created. Please fill it with your Schwab API credentials and run the script again.")
        except Exception as e:
            logging.error(f"Failed to create sample 'creds.yml': {e}")
        sys.exit(1)

    # Load credentials
    app_key, app_secret, callback_url, token_path = creds_manager.get_credentials()

    logging.info("Credentials loaded successfully.")
    logging.info(f"Token will be saved to: {token_path}")

    try:
        # This will automatically open a browser for authentication
        # and start a local server to capture the redirect.
        client = schwabdev.Client(
            app_key=app_key,
            app_secret=app_secret,
            callback_url=callback_url,
            tokens_file=token_path,
            capture_callback=True,  # Important: This enables the web server
            use_session=True
        )

        # The schwabdev library handles the browser opening and token saving.
        # A message will be printed to the console with the URL to open.
        logging.info("Please follow the instructions in your web browser to authenticate.")
        logging.info("Waiting for authentication to complete...")

        # The client constructor with capture_callback=True blocks until the token is received.
        # We can test the connection to confirm it worked.
        if client.is_authenticated():
             logging.info("Authentication successful! Token has been saved.")
        else:
             # This part might not be reached if the auth fails and raises an exception,
             # but it's good practice to have it.
             logging.error("Authentication failed. Please check your credentials and try again.")
             sys.exit(1)

    except Exception as e:
        logging.error(f"An error occurred during authentication: {e}")
        sys.exit(1)

if __name__ == "__main__":
    main()
