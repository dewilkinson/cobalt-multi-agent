import asyncio
import os
import json
from datetime import datetime, timezone, timedelta

# Mocking the api logic to see what it filters
with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json', 'r') as f:
    cache = json.load(f)

account_id = list(cache.keys())[0]
activities = cache[account_id]
activities_chronological = list(reversed(activities))

start_date = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
end_date = datetime.now(timezone.utc).strftime("%Y-%m-%d")

results = []
for act in activities_chronological:
    action = act.get('type', act.get('action', 'N/A')).upper()
    if action not in ["BUY", "SELL", "BOUGHT", "SOLD", "BTO", "STC", "BTC", "STO", "REINVEST", "DIVIDEND"]:
        continue
        
    # robust symbol extraction
    if isinstance(act.get('symbol'), dict):
        sym = act['symbol'].get('symbol', 'N/A')
    elif isinstance(act.get('universal_symbol'), dict):
        sym = act['universal_symbol'].get('symbol', act.get('symbol', 'N/A'))
    else:
        sym = act.get('symbol', 'N/A')
        
    if isinstance(sym, dict):
        sym = sym.get('symbol', 'N/A')
        
    if sym == 'N/A': continue
    sym_raw = str(sym).upper().replace('-USD', '').replace('*', '')
    if sym_raw == 'SPAXX': continue

    placed_time = act.get('trade_date', act.get('time_placed', ''))
    date_only = placed_time[:10] if placed_time else "Unknown"
    
    if start_date <= date_only <= end_date or date_only == "Unknown":
        results.append(act)

print(f"Results len: {len(results)}")
print(f"Sample: {results[0] if results else 'None'}")
