import requests
res = requests.get('http://localhost:8000/api/brokerage/history', params={'account_id': 'Rollover IRA *5513', 'start_date': '2026-04-01', 'end_date': '2026-04-06'}).json()
print('SUM:', res['realized_pnl_summary'])
print('NUM TRADES:', len(res['closed_positions']))
print('AMCI IN API:', [c for c in res['closed_positions'] if c['symbol'] == 'AMCI'])

