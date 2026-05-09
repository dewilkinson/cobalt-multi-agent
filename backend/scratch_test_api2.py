import requests
try:
    res = requests.get('http://127.0.0.1:8000/api/brokerage/history', params={'account_id': 'Rollover IRA *5513', 'start_date': '2026-05-06', 'end_date': '2026-05-06'})
    data = res.json()
    closed = data.get('closed_positions', [])
    print(f"Total closed positions returned: {len(closed)}")
    for c in closed:
        print(c.get('symbol'), c.get('close_date'))
except Exception as e:
    print(f"Error: {e}")
