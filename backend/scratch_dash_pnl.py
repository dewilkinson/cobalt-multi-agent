import sys
sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache

d = BrokerageCache._load_cache()
acct = d.get('Rollover IRA *5513', {})

realized_pnl = BrokerageCache.calculate_realized_pnl('Rollover IRA *5513', '2026-05-06', '2026-05-06')['total_pnl']
unrealized_pnl = 0.0

for p in acct.get('positions', []):
    unrealized_pnl += float(p.get('todays_gl_dol') or 0.0)

print(f"Realized: {realized_pnl}")
print(f"Unrealized: {unrealized_pnl}")
print(f"Total: {realized_pnl + unrealized_pnl}")
