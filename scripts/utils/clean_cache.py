import json
import os
import sys

sys.path.append(r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend')
from src.services.brokerage_cache import BrokerageCache
from src.services.atp_importer import parse_atp_history, parse_atp_orders

cache_file = r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\data\brokerage_cache.json'
with open(cache_file, 'r') as f:
    data = json.load(f)

# Clear activities
for acct in data.values():
    if isinstance(acct, dict):
        acct['activities'] = []
with open(cache_file, 'w') as f:
    json.dump(data, f, indent=2)

print("Cache cleared. Re-importing...")

hist = parse_atp_history(r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\data\dropzone\archive\Accounts_History (27).csv')
orders = parse_atp_orders(r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\data\dropzone\archive\Orders_All_Accounts.csv')

for acct, acts in hist.items():
    if acts:
        BrokerageCache.merge_activities(acct, acts)
        print(f"Merged {len(acts)} hist activities for {acct}")

for acct, acts in orders.items():
    if acts:
        BrokerageCache.merge_activities(acct, acts)
        print(f"Merged {len(acts)} order activities for {acct}")

# Now dedupe
with open(cache_file, 'r') as f: data = json.load(f)
for acct, acct_data in data.items():
    if not isinstance(acct_data, dict): continue
    activities = acct_data.get('activities', [])
    atp_acts = [a for a in activities if a.get('id', '').startswith('ATP-')]
    hist_acts = [a for a in activities if a.get('id', '').startswith('HIST-')]
    other_acts = [a for a in activities if not a.get('id', '').startswith('ATP-') and not a.get('id', '').startswith('HIST-')]
    
    # We want to remove HIST trades if there is an ATP trade for the same symbol, date, qty, action
    atp_lookup = {f"{a.get('symbol', {}).get('symbol', '')}_{a.get('trade_date', '')[:10]}_{a.get('units', 0)}_{a.get('type', '')}": a for a in atp_acts}
    kept_hist = [h for h in hist_acts if f"{h.get('symbol', {}).get('symbol', '')}_{h.get('trade_date', '')[:10]}_{h.get('units', 0)}_{h.get('type', '')}" not in atp_lookup]
    
    final_acts = atp_acts + kept_hist + other_acts
    final_acts.sort(key=lambda x: x.get('trade_date', ''), reverse=True)
    acct_data['activities'] = final_acts
    print(f'Account {acct}: Kept {len(atp_acts)} ATP, {len(kept_hist)} HIST. Removed {len(hist_acts) - len(kept_hist)} redundant HIST.')
with open(cache_file, 'w') as f: json.dump(data, f, indent=2)

pnl = BrokerageCache.calculate_realized_pnl('Rollover IRA *5513', '2026-04-30', '2026-04-30')
print(f"Recalculated Realized PnL: {pnl}")
