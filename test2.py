import json
with open('data/brokerage_cache.json', encoding='utf-8') as f:
    cache = json.load(f)
for acts in cache.values():
    for act in acts[:20]:
        sym = ''
        if isinstance(act.get('symbol'), dict):
            sym = act['symbol'].get('symbol')
        elif isinstance(act.get('universal_symbol'), dict):
            sym = act['universal_symbol'].get('symbol')
        else:
            sym = act.get('symbol')
        if sym in ['UNH', 'XLE', 'PTEN']:
            print(f"sym: {sym}, trade_date: {act.get('trade_date')}, time_placed: {act.get('time_placed')}")
