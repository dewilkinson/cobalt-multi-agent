import json
import sys
sys.path.append('c:/github/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache

d = BrokerageCache._load_cache()

for account, acct_data in d.items():
    acts = acct_data.get('activities', [])
    acts = sorted(acts, key=lambda a: a.get('trade_date', a.get('time_placed', '')))
    
    tax_lots = {}
    orphaned_ids = set()
    
    for act in acts:
        action = act.get('type', act.get('action', '')).upper()
        sym = act.get('symbol', {}).get('symbol')
        if not sym: continue
        sym = sym.upper()
        qty = float(act.get('units', 0))
        status = str(act.get('status', 'Executed')).upper()
        
        if action not in ['BUY', 'SELL'] or status in ['OPEN', 'PENDING', 'CANCELED']: continue
        
        if action == 'BUY':
            if sym not in tax_lots: tax_lots[sym] = []
            tax_lots[sym].append({'qty': qty})
        elif action == 'SELL':
            sell_qty = qty
            matched = 0
            while sell_qty > 0.0001 and tax_lots.get(sym, []):
                lot = tax_lots[sym][0]
                if lot['qty'] <= sell_qty:
                    matched += lot['qty']
                    sell_qty -= lot['qty']
                    tax_lots[sym].pop(0)
                else:
                    matched += sell_qty
                    lot['qty'] -= sell_qty
                    sell_qty = 0
            if matched == 0:
                orphaned_ids.add(act.get('id'))
                
    if orphaned_ids:
        print(f"Removing {len(orphaned_ids)} orphaned SELL trades from {account}")
        acct_data['activities'] = [a for a in acct_data.get('activities', []) if a.get('id') not in orphaned_ids]

BrokerageCache._save_cache(d)
print("Done.")
