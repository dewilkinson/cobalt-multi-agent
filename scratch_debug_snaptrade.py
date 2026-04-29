import os, sys, json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv("C:\\github\\cobalt-multi-agent\\backend\\.env", override=True)

from snaptrade_client import SnapTrade

client = SnapTrade(
    client_id=os.getenv("SNAPTRADE_CLIENT_ID"),
    consumer_key=os.getenv("SNAPTRADE_CONSUMER_KEY")
)
uid = os.getenv("SNAPTRADE_USER_ID")
usecret = os.getenv("SNAPTRADE_USER_SECRET")

accounts = getattr(client.account_information.list_user_accounts(user_id=uid, user_secret=usecret), 'body', [])
if not accounts:
    print("No accounts")
    sys.exit()

acc_id = accounts[0].get('id')
print(f"Using account: {accounts[0].get('name')}")

today_str = datetime.now(timezone.utc).strftime("%Y-%m-%d")
yesterday_str = (datetime.now(timezone.utc) - timedelta(days=2)).strftime("%Y-%m-%d")

print(f"Fetching from {yesterday_str} to {today_str}")

acts = client.transactions_and_reporting.get_activities(
    user_id=uid, user_secret=usecret, accounts=acc_id, start_date=yesterday_str, end_date=today_str
)
acts = getattr(acts, 'body', acts)

print("Recent activities:")
for act in acts[:5]:
    print(act)
