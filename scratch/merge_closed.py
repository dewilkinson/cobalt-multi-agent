import sys
sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.atp_importer import parse_atp_closed_positions
from src.services.brokerage_cache import BrokerageCache
new_closed = parse_atp_closed_positions('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/dropzone/archive/Closed_Positions_Rollover_IRA__5513.csv')
existing_closed = BrokerageCache.get_closed_positions('Rollover IRA *5513') or []
existing_sigs = {f"{c['symbol']}_{c['qty']}_{c['pnl']}" for c in existing_closed}
added = 0
for c in new_closed.get('Rollover IRA *5513', []):
    sig = f"{c['symbol']}_{c['qty']}_{c['pnl']}"
    if sig not in existing_sigs:
        existing_closed.append(c)
        existing_sigs.add(sig)
        added += 1
BrokerageCache.replace_closed_positions('Rollover IRA *5513', existing_closed)
print(f'Successfully merged {added} new YTD trades. Total explicit closed positions: {len(existing_closed)}')

