import requests
try:
    res = requests.get('http://127.0.0.1:8000/api/brokerage/history', params={'account_id': 'Rollover IRA *5513', 'start_date': '2026-05-06', 'end_date': '2026-05-06'})
    data = res.json()
    print('Positions:', len(data.get('positions', [])))
    print('Closed Positions:', len(data.get('closed_positions', [])))
except Exception as e:
    print(f"Error: {e}")
