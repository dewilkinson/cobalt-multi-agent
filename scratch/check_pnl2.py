import sys
sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache
import json

cache = BrokerageCache._load_cache()
for account_id in cache.keys():
    print(f"=== Account: {account_id} ===")
    res = BrokerageCache.calculate_realized_pnl(account_id, '2026-05-12', '2026-05-12')
    print(f"Total PnL: {res['total_pnl']}")
    for t in res['closed_trades']:
        print(f"{t['symbol']}: Qty {t['qty']} | Buy: {t['buy_price']} -> Sell: {t['sell_price']} | PnL: {t['pnl']}")
