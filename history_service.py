import logging
from datetime import datetime, timedelta

# Configure logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HistoryService:
    """Service for fetching historical price data."""

    def __init__(self, schwab_client=None):
        """
        Initialize the history service.

        Args:
            schwab_client: Authenticated schwabdev client instance.
        """
        self.schwab_client = schwab_client
        if schwab_client:
            logger.info("History service initialized with Schwab client.")
        else:
            logger.info("History service initialized without Schwab client.")

    def set_client(self, schwab_client):
        """
        Set the schwabdev client instance after initialization.

        Args:
            schwab_client: Authenticated schwabdev client instance.
        """
        self.schwab_client = schwab_client
        logger.info("Schwab client has been set in HistoryService.")

    def fetch_history_for_symbol(self, symbol: str) -> dict:
        """
        Fetches the 30-minute (10 days) and daily (15 days) price history for a symbol.

        Args:
            symbol: The stock symbol (e.g., 'AAPL').

        Returns:
            A dictionary containing the fetched data or an error message.
        """
        if not self.schwab_client:
            logger.error("Schwab client not set in history service. Cannot fetch data.")
            return {"success": False, "error": "Schwab client not initialized."}

        try:
            logger.info(f"Fetching historical data for symbol: {symbol}...")

            # 1. Fetch 30-minute data for the past 10 days.
            history_30m_response = self.schwab_client.price_history(
                symbol=symbol,
                periodType='day',
                period=10,
                frequencyType='minute',
                frequency=30,
                needExtendedHoursData=False
            )
            history_30m_json = history_30m_response.json() if history_30m_response.ok else {'error': history_30m_response.text}

            if not history_30m_response.ok or history_30m_json.get('empty', False):
                logger.warning(f"Could not retrieve 30-minute history for {symbol}. Response: {history_30m_json}")


            # 2. Fetch daily data for the past 15 days.
            # The API doesn't support a 30-day period directly, so we use a date range.
            end_date = datetime.now()
            start_date = end_date - timedelta(days=30)

            history_daily_response = self.schwab_client.price_history(
                symbol=symbol,
                periodType='year',
                frequencyType='daily',
                startDate=int(start_date.timestamp() * 1000), # Epoch milliseconds
                endDate=int(end_date.timestamp() * 1000), # Epoch milliseconds
                needExtendedHoursData=False
            )
            history_daily_json = history_daily_response.json() if history_daily_response.ok else {'error': history_daily_response.text}

            if not history_daily_response.ok or history_daily_json.get('empty', False):
                logger.warning(f"Could not retrieve daily history for {symbol}. Response: {history_daily_json}")
                # We can still return success if we got the 30m data. The frontend can handle missing data.

            if not history_30m_response.ok and not history_daily_response.ok:
                 return {"success": False, "error": f"Failed to retrieve any historical data for {symbol}."}

            logger.info(f"Successfully fetched historical data for {symbol}.")
            return {
                "success": True,
                "data": {
                    "data_30m": history_30m_json if history_30m_response.ok else None,
                    "data_daily": history_daily_json if history_daily_response.ok else None
                }
            }

        except Exception as e:
            error_msg = f"An exception occurred while fetching history for {symbol}: {e}"
            logger.exception(error_msg)
            return {"success": False, "error": error_msg}

# Singleton instance to be used by the server
history_service = HistoryService()
