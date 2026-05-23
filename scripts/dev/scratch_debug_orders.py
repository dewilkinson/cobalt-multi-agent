import os, sys, json
from dotenv import load_dotenv
load_dotenv('C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent\\backend\\.env', override=True)
from snaptrade_client import SnapTrade
client = SnapTrade(client_id=os.getenv('SNAPTRADE_CLIENT_ID'), consumer_key=os.getenv('SNAPTRADE_CONSUMER_KEY'))
uid = os.getenv('SNAPTRADE_USER_ID')
usecret = os.getenv('SNAPTRADE_USER_SECRET')
accounts = getattr(client.account_information.list_user_accounts(user_id=uid, user_secret=usecret), 'body', [])
if accounts:
    acc_id = accounts[0].get('id')
    try:
        orders = getattr(client.account_information.get_user_account_orders(user_id=uid, user_secret=usecret, account_id=acc_id, state='executed'), 'body', [])
        print('Executed orders count:', len(orders))
        if orders: print(orders[0])
    except Exception as e: print(e)
