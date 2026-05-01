import json
from src.services.brokerage_cache import BrokerageCache
activities = BrokerageCache.get_activities('Health Savings Account *6937')
activities_chronological = list(reversed(activities))
open_positions = {}
for act in activities_chronological:
    action = act.get('type', act.get('action', 'N/A')).upper()
    if action not in ['BUY', 'SELL']: continue
    sym_raw = act.get('symbol', 'N/A')
    if isinstance(sym_raw, dict): sym_raw = sym_raw.get('symbol')
    qty = float(act.get('units', 0))
    if sym_raw not in open_positions: open_positions[sym_raw] = {'quantity': 0.0}
    if action == 'BUY': open_positions[sym_raw]['quantity'] += qty
    elif action == 'SELL': open_positions[sym_raw]['quantity'] -= qty
print(open_positions)
