import sys, json
sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache

account_id = 'Rollover IRA *5513'
start_date = '2026-04-01'
end_date = '2026-04-06'

realized_pnl_data = BrokerageCache.calculate_realized_pnl(account_id, start_date, end_date)
closed_positions = realized_pnl_data['closed_trades']
print('FIFO AMCI:', [c for c in closed_positions if c['symbol'] == 'AMCI'])

explicit_closed = BrokerageCache.get_closed_positions(account_id)
print('EXPLICIT AMCI:', [c for c in explicit_closed if c['symbol'] == 'AMCI'])

filtered_explicit = []
for cp in explicit_closed:
    cp_date = str(cp.get('close_date', ''))[:10]
    if not cp_date or (start_date <= cp_date <= end_date):
        filtered_explicit.append(cp)
print('FILTERED EXPLICIT AMCI:', [c for c in filtered_explicit if c['symbol'] == 'AMCI'])

