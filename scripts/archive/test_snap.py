
import os
from dotenv import load_dotenv
load_dotenv('backend/.env')
from snaptrade_client import SnapTrade
client = SnapTrade(client_id=os.getenv('SNAPTRADE_CLIENT_ID'), consumer_key=os.getenv('SNAPTRADE_CONSUMER_KEY'))
try:
    res = client.account_information.list_user_accounts(user_id=os.getenv('SNAPTRADE_USER_ID'), user_secret=os.getenv('SNAPTRADE_USER_SECRET'))
    print('Success')
except Exception as e:
    print('Error:', e)

