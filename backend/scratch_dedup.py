import json
import sys
sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache

d = BrokerageCache._load_cache()
total_removed = 0

for account, data in d.items():
    acts = data.get('activities', [])
    
    # Let's deduplicate based on symbol, type, units, price, and trade_date (up to the minute)
    unique_acts = []
    seen = set()
    
    removed = 0
    
    # To prioritize ATP over HIST, we can sort ATP first
    acts.sort(key=lambda x: (0 if x.get('id', '').startswith('ATP') else 1))
    
    for act in acts:
        # Some acts might not have all fields, handle gracefully
        sym = act.get('symbol', {}).get('symbol') if isinstance(act.get('symbol'), dict) else act.get('symbol')
        act_type = act.get('type')
        units = act.get('units')
        price = act.get('price')
        # match up to the minute or hour? The time might be slightly different. Let's just match up to the day for exact same qty and price?
        date = act.get('trade_date', '')[:10] # YYYY-MM-DD
        
        sig = (sym, act_type, units, price, date)
        if sig in seen:
            removed += 1
            continue
        
        seen.add(sig)
        unique_acts.append(act)
        
    if removed > 0:
        print(f"Removed {removed} duplicate/orphaned trades from {account}")
        data['activities'] = unique_acts
        total_removed += removed

if total_removed > 0:
    BrokerageCache._save_cache(d)
    print(f"Total removed: {total_removed}")
else:
    print("No orphaned/duplicate trades found.")
