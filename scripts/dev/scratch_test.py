import os
from dotenv import load_dotenv
load_dotenv('backend/.env')
from snaptrade_client import SnapTrade

cid = os.getenv('SNAPTRADE_CLIENT_ID', '')
ckey = os.getenv('SNAPTRADE_CONSUMER_KEY', '')
uid = os.getenv('SNAPTRADE_USER_ID', '')
usecret = os.getenv('SNAPTRADE_USER_SECRET', '')

client = SnapTrade(client_id=cid, consumer_key=ckey)
try:
    res = client.account_information.list_user_accounts(user_id=uid, user_secret=usecret)
    
    # We need to see what `res` looks like
    print(res)
    print("Type of res:", type(res))
    
    accounts = getattr(res, 'body', res)
    print("Type of accounts:", type(accounts))
    
    if hasattr(accounts, '__iter__'):
        for a in accounts:
            print("Account type:", type(a))
            if hasattr(a, 'to_dict'):
                print(a.to_dict())
            elif isinstance(a, dict):
                print(a)
            else:
                print(dir(a))
except Exception as e:
    print("ERROR:", e)
