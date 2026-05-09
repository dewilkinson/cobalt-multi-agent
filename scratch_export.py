import json
import csv
from datetime import datetime
import os

cache_path = 'C:/github/cobalt-multi-agent/data/archive/BrokerageCacheDailyBackup.json'
output_path = 'C:/github/cobalt-multi-agent/data/exports/tradezella-import-this-week.csv'

def extract_trades():
    with open(cache_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    trades_to_export = []
    
    # This week dates
    valid_dates = ['2026-05-04', '2026-05-05', '2026-05-06', '2026-05-07', '2026-05-08']
    
    for account_name, account_data in data.items():
        if 'activities' in account_data:
            for activity in account_data['activities']:
                if activity.get('status') != 'Executed':
                    continue
                
                trade_date_str = activity.get('trade_date', '')
                if not any(trade_date_str.startswith(d) for d in valid_dates):
                    continue
                    
                # Format: "2026-05-01T15:21:09.000Z"
                dt = datetime.strptime(trade_date_str, "%Y-%m-%dT%H:%M:%S.000Z")
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
                
    trades_to_export.sort(key=lambda x: (x['Date'], x['Time'], x['Symbol'], 0 if x['Buy/Sell'].lower() == 'buy' else 1))
    
    tz_headers = ['Account Name', 'Date&Time', 'Date', 'Time', 'Symbol', 'Buy/Sell', 'Quantity', 'Price', 'Spread', 'Expiration', 'Strike', 'Call/Put', 'Commission', 'Fees']
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers)
        writer.writeheader()
        writer.writerows(trades_to_export)
        
    print(f'Success! {len(trades_to_export)} trades exported to {output_path}')

if __name__ == '__main__':
    extract_trades()
