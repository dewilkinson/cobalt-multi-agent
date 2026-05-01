from src.services.brokerage_cache import BrokerageCache
acts = BrokerageCache.get_activities('Rollover IRA *5513')
today_sells = [a for a in acts if a.get('trade_date', '').startswith('2026-04-30') and a.get('type') in ['SELL', 'SOLD']]
for s in today_sells:
    print(f"{s['trade_date']} | {s['symbol'].get('symbol', '')} | QTY: {s['units']} | Prc: {s['price']}")
