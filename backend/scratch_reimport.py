import sys
import json
import os
import shutil

sys.path.append('c:/github/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache
from src.services.atp_importer import parse_atp_orders

# 1. Load cache and purge today's activities
cache = BrokerageCache._load_cache()
for account, data in cache.items():
    acts = data.get('activities', [])
    clean_acts = [a for a in acts if '2026-05-06' not in a.get('trade_date', a.get('time_placed', ''))]
    data['activities'] = clean_acts
BrokerageCache._save_cache(cache)

# 2. Re-parse the Orders CSV and merge
orders_csv = 'c:/github/cobalt-multi-agent/data/dropzone/archive/Orders_All_Accounts.csv'
orders_data = parse_atp_orders(orders_csv)
for account, acts in orders_data.items():
    if acts:
        # We only want today's activities from this file just in case
        todays_acts = [a for a in acts if '2026-05-06' in a.get('trade_date', a.get('time_placed', ''))]
        if todays_acts:
            BrokerageCache.merge_activities(account, todays_acts)
            print(f"Re-imported {len(todays_acts)} activities for {account}")

print("Done cleaning and reimporting.")
