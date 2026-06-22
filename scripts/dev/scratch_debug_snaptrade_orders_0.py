import os, sys, json
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

load_dotenv("C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent\\backend\\.env", override=True)

from snaptrade_client import SnapTrade

client = SnapTrade(
    client_id=os.getenv("SNAPTRADE_CLIENT_ID"),
    consumer_key=os.getenv("SNAPTRADE_CONSUMER_KEY")
)
uid = os.getenv("SNAPTRADE_USER_ID")
usecret = os.getenv("SNAPTRADE_USER_SECRET")

accounts = getattr(client.account_information.list_user_accounts(user_id=uid, user_secret=usecret), 'body', [])
if not accounts:
    sys.exit()

acc_id = accounts[0].get('id')

print("Fetching ALL orders for account:", acc_id)
try:
    orders = client.account_information.get_user_account_orders(
        user_id=uid, user_secret=usecret, account_id=acc_id, state="all"
    )
    orders = getattr(orders, 'body', orders)
    print("Found", len(orders), "orders")
    for o in orders[:5]:
        print(o)
except Exception as e:
    print(e)
