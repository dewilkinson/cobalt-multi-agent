import sys, json
sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.atp_importer import parse_atp_closed_positions, parse_atp_positions
from src.services.brokerage_cache import BrokerageCache

# 1. Clear Cache
cache = BrokerageCache._load_cache()
account = 'Rollover IRA *5513'
cache[account] = {'activities': [], 'positions': [], 'closed_positions': [], 'balances': cache.get(account, {}).get('balances', {})}
BrokerageCache._save_cache(cache)
print('Cleared activities, positions, and closed_positions for', account)

# 2. Parse and merge closed positions
closed_2025 = parse_atp_closed_positions('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/dropzone/2025.csv').get(account, [])
closed_ytd = parse_atp_closed_positions('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/dropzone/YTD.csv').get(account, [])

combined_closed = []
seen_sigs = set()
for c in closed_2025 + closed_ytd:
    sig = f"{c['symbol']}_{c['qty']}_{c['pnl']}"
    if sig not in seen_sigs:
        combined_closed.append(c)
        seen_sigs.add(sig)

BrokerageCache.replace_closed_positions(account, combined_closed)
print(f'Imported {len(combined_closed)} explicit closed positions')

# 3. Restore explicit open positions from today's archive
pos_data = parse_atp_positions('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/dropzone/archive/Positions_Rollover_IRA__5513.csv').get(account, [])
if pos_data:
    BrokerageCache.set_positions(account, pos_data)
    print(f'Restored {len(pos_data)} explicit open positions')

