from tradingview_screener import Query, col

fields = ['name', 'close']
q = (Query()
     .set_markets('america')
     .select('name', 'close', 'change', 'change_from_open')
     .where(col('exchange').isin(['NASDAQ', 'NYSE']), col('type') == 'stock', col('subtype') == 'common', col('close').between(1, 20), col('market_cap_basic').between(100_000_000, 2_000_000_000), col('change') > 3)
     .limit(5))

print(q.get_scanner_data()[1])
