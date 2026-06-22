import json
from datetime import datetime

with open("scratch/snaptrade_raw_activities.json", "r", encoding="utf-8") as f:
    data = json.load(f)

weekly_trades = []
ignore_symbols = {"CASH", "FZFXX", "SPAXX", "FCASH", "FDRXX"}

for act in data:
    # Get transaction type/action
    action = act.get("type") or act.get("action")
    if action not in ["BUY", "SELL"]:
        continue
        
    # Get symbol
    sym = ""
    if 'universal_symbol' in act and act['universal_symbol']:
        sym = act['universal_symbol'].get('symbol', '')
    elif 'symbol' in act and act['symbol'] and isinstance(act['symbol'], dict):
        sym = act['symbol'].get('symbol', '')
    elif 'symbol' in act and isinstance(act['symbol'], str):
        sym = act['symbol']
        
    if not sym or sym in ignore_symbols:
        continue
        
    # Get date
    date_str = act.get('trade_date') or act.get('date') or act.get('timestamp')
    if not date_str:
        continue
        
    try:
        dt = datetime.strptime(date_str[:10], "%Y-%m-%d")
        # Check if date is in the week of May 18-22, 2026
        # May 18 is Monday, May 22 is Friday
        if dt.year == 2026 and dt.month == 5 and (18 <= dt.day <= 22):
            units = act.get('units') or act.get('quantity') or 0.0
            price = act.get('price') or 0.0
            account_name = act.get('account', {}).get('name', 'Unknown Account')
            
            # SnapTrade sell units are negative, make units absolute
            units = abs(float(units))
            price = float(price)
            
            weekly_trades.append({
                "account": account_name,
                "symbol": sym,
                "action": action,
                "units": units,
                "price": price,
                "date": date_str[:10]
            })
    except Exception as e:
        print(f"Error parsing date {date_str}: {e}")

# Sort by date, then symbol, then action
weekly_trades.sort(key=lambda x: (x["date"], x["symbol"], x["action"]))

print(f"Found {len(weekly_trades)} trade activities for this week:")
for t in weekly_trades:
    print(f"[{t['date']}] {t['account']} | {t['action']} {t['units']} {t['symbol']} @ ${t['price']}")
