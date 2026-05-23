import json
import csv
from datetime import datetime
import os

cache_path = 'C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/archive/BrokerageCacheDailyBackup.json'
output_path = 'C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/exports/tradezella-import-this-week.csv'

def extract_trades():
    with open(cache_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    trades_to_export = []
    
    # This week dates
    valid_dates = ['2026-05-18', '2026-05-19', '2026-05-20', '2026-05-21', '2026-05-22']
    
    for account_name, account_data in data.items():
        if account_name != "Rollover IRA *5513":
            continue
        if 'activities' in account_data:
            for activity in account_data['activities']:
                if activity.get('status') != 'Executed':
                    continue
                
                trade_date_str = activity.get('trade_date', '')
                if not any(trade_date_str.startswith(d) for d in valid_dates):
                    continue
                    
                # Format: "2026-05-01T15:21:09.000Z"
                # Some times might have .000Z, others might have microseconds or be slightly different
                # Let's handle different ISO formats safely
                try:
                    if '.' in trade_date_str:
                        dt = datetime.strptime(trade_date_str, "%Y-%m-%dT%H:%M:%S.%fZ")
                    else:
                        dt = datetime.strptime(trade_date_str.replace("Z", ""), "%Y-%m-%dT%H:%M:%S")
                except Exception:
                    try:
                        dt = datetime.strptime(trade_date_str, "%Y-%m-%dT%H:%M:%S.000Z")
                    except Exception:
                        dt = datetime.fromisoformat(trade_date_str.replace("Z", "+00:00"))
                        
                tz_date = dt.strftime("%m/%d/%Y")
                tz_time = dt.strftime("%H:%M:%S")
                
                action = activity.get('type', '').capitalize()
                
                trades_to_export.append({
                    'Account Name': account_name,
                    'Date&Time': '',
                    'Date': tz_date,
                    'Time': tz_time,
                    'Symbol': activity['symbol']['symbol'] if isinstance(activity.get('symbol'), dict) else activity.get('symbol', ''),
                    'Buy/Sell': action,
                    'Quantity': float(activity['units']),
                    'Price': float(activity['price']),
                    'Spread': 'Stock',
                    'Expiration': '',
                    'Strike': '',
                    'Call/Put': '',
                    'Commission': 0,
                    'Fees': 0
                })
                
    trades_to_export.sort(key=lambda x: (datetime.strptime(f"{x['Date']} {x['Time']}", "%m/%d/%Y %H:%M:%S"), x['Symbol'], 0 if x['Buy/Sell'].lower() == 'buy' else 1))
    
    tz_headers = ['Account Name', 'Date&Time', 'Date', 'Time', 'Symbol', 'Buy/Sell', 'Quantity', 'Price', 'Spread', 'Expiration', 'Strike', 'Call/Put', 'Commission', 'Fees']
    
    # Define all target export files
    export_paths = [
        output_path,  # data/exports/tradezella-import-this-week.csv
        output_path.replace('tradezella-import-this-week.csv', 'tradezella-import.csv'),  # data/exports/tradezella-import.csv
        output_path.replace('/data/exports/tradezella-import-this-week.csv', '/backend/data/exports/tradezella-import-this-week.csv'),  # backend/data/exports/tradezella-import-this-week.csv
        output_path.replace('/data/exports/tradezella-import-this-week.csv', '/backend/data/exports/tradezella-import.csv')  # backend/data/exports/tradezella-import.csv
    ]
    
    print(f'Writing {len(trades_to_export)} trades to exports:')
    for p in export_paths:
        os.makedirs(os.path.dirname(p), exist_ok=True)
        with open(p, 'w', newline='', encoding='utf-8') as f:
            writer = csv.DictWriter(f, fieldnames=tz_headers)
            writer.writeheader()
            writer.writerows(trades_to_export)
        print(f'  - {p}')

if __name__ == '__main__':
    extract_trades()
