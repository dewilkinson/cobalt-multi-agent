import os
from snaptrade_client import SnapTrade
from langchain_core.tools import tool
from langchain_core.runnables import RunnableConfig
import logging
from datetime import datetime, timedelta
from src.config.configuration import Configuration

logger = logging.getLogger(__name__)

def _get_client_and_creds(config: RunnableConfig):
    configurable = Configuration.from_runnable_config(config)
    settings = configurable.snaptrade_settings if configurable.snaptrade_settings else {}
    
    # Priority: 1. Request Settings, 2. Environment Variables
    client_id = settings.get("SNAPTRADE_CLIENT_ID") or os.getenv("SNAPTRADE_CLIENT_ID")
    consumer_key = settings.get("SNAPTRADE_CONSUMER_KEY") or os.getenv("SNAPTRADE_CONSUMER_KEY")
    user_id = settings.get("SNAPTRADE_USER_ID") or os.getenv("SNAPTRADE_USER_ID")
    user_secret = settings.get("SNAPTRADE_USER_SECRET") or os.getenv("SNAPTRADE_USER_SECRET")
    mock_broker = settings.get("MOCK_BROKER") or os.getenv("MOCK_BROKER")
    
    client = None
    if client_id and consumer_key:
        client = SnapTrade(
            client_id=client_id,
            consumer_key=consumer_key
        )
    
    return client, user_id, user_secret, mock_broker

@tool
def get_brokerage_accounts(config: RunnableConfig):
    """
    Get a list of all brokerage accounts connected via SnapTrade.
    Use this to find the account_id (UUID) for the user's brokerage accounts (e.g., Fidelity).
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if mock_broker == "true":
             logger.info("MOCK_BROKER=true, returning simulated data.")
             return [
                 {"id": "mock-fidelity-1", "name": "Fidelity Rollover IRA", "institution": "Fidelity"},
                 {"id": "mock-fidelity-2", "name": "Fidelity Individual", "institution": "Fidelity"}
             ]
        return "[ERROR]: SnapTrade credentials (SNAPTRADE_CLIENT_ID, SNAPTRADE_CONSUMER_KEY, SNAPTRADE_USER_ID, SNAPTRADE_USER_SECRET) are not fully configured."

    try:
        logger.info(f"Fetching SnapTrade accounts for user {user_id}")
        api_response = client.account_information.list_user_accounts(
            user_id=user_id,
            user_secret=user_secret
        )
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling list_user_accounts: {e}\n"

@tool
def get_brokerage_balance(account_id: str, config: RunnableConfig):
    """
    Get the current cash balance and currency information for a specific brokerage account.
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if mock_broker == "true":
             logger.info("MOCK_BROKER=true, returning simulated balance.")
             return [
                 {"currency": {"code": "USD", "name": "US Dollar"}, "cash": 25420.69, "amount": 25420.69}
             ]
        return "[ERROR]: SnapTrade credentials are not fully configured."

    try:
        logger.info(f"Fetching balance for account {account_id}")
        api_response = client.account_information.get_user_account_balance(
            user_id=user_id,
            user_secret=user_secret,
            account_id=account_id
        )
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling get_user_account_balance: {e}\n"

@tool
def get_brokerage_history(account_id: str, days: int = 30, config: RunnableConfig = None):
    """
    Get historical trading logs and activities (buys, sells, dividends, etc.) for a specific brokerage account.
    
    Args:
        account_id: The UUID of the account (retrieve this using get_brokerage_accounts).
        days: Number of days of historical data to retrieve (default is 30).
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if mock_broker == "true":
             logger.info("MOCK_BROKER=true, returning simulated history.")
             return [
                 {"date": "2026-03-20", "symbol": "AAPL", "action": "BUY", "quantity": 10, "price": 150.00},
                 {"date": "2026-03-15", "symbol": "MSFT", "action": "SELL", "quantity": 5, "price": 400.00},
                 {"date": "2026-03-01", "symbol": "CASH", "action": "DEPOSIT", "quantity": 1000, "price": 1.00}
             ]
        return "[ERROR]: SnapTrade credentials are not fully configured."

    # Calculate date range
    end_date = datetime.now()
    start_date = end_date - timedelta(days=days)

    try:
        logger.info(f"Fetching activities for account {account_id} over the last {days} days")
        api_response = client.transactions_and_reporting.get_activities(
            user_id=user_id,
            user_secret=user_secret,
            accounts=account_id,
            start_date=start_date.strftime("%Y-%m-%d"),
            end_date=end_date.strftime("%Y-%m-%d")
        )
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling get_activities: {e}\n"

@tool
def get_brokerage_statements(account_id: str, config: RunnableConfig):
    """
    Get a list of available electronic statements (PDF URLs) for a specific brokerage account.
    """
    client, user_id, user_secret, mock_broker = _get_client_and_creds(config)

    if not client or not user_id or not user_secret:
        if mock_broker == "true":
             logger.info("MOCK_BROKER=true, returning simulated statements.")
             return [
                 {"date": "2026-02-28", "type": "MONTHLY_STATEMENT", "url": "https://example.com/mock-statement-feb-2026.pdf"},
                 {"date": "2026-01-31", "type": "MONTHLY_STATEMENT", "url": "https://example.com/mock-statement-jan-2026.pdf"}
             ]
        return "[ERROR]: SnapTrade credentials are not fully configured."

    try:
        logger.info(f"Fetching statements for account {account_id}")
        api_response = client.account_information.list_user_account_statements(
            user_id=user_id,
            user_secret=user_secret,
            account_id=account_id
        )
        return api_response
    except Exception as e:
        logger.error(f"SnapTrade API Error: {e}")
        return f"[ERROR]: Exception when calling list_user_account_statements: {e}\n"
