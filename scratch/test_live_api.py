import urllib.request
import json

url = 'http://127.0.0.1:8000/api/brokerage/history?account_id=TradingView%20Paper%20Futures&start_date=2026-07-21&end_date=2026-07-21'
req = urllib.request.urlopen(url)
data = json.loads(req.read().decode('utf-8'))

print(f"Today Realized PnL: ${data.get('today_realized_pnl'):,.2f}")
print(f"Realized PnL Summary: ${data.get('realized_pnl_summary'):,.2f}")
print(f"Closed Positions Count: {len(data.get('closed_positions', []))}")
