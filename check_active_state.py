import requests
try:
    res = requests.get('http://127.0.0.1:3000/api/vli/active-state').json()
    shield = [c for c in res.get('scanner_results', {}).get('candidates', []) if c.get('tier') == 'SHIELD']
    sniper = [c for c in res.get('scanner_results', {}).get('candidates', []) if c.get('tier') == 'SNIPER']
    print(f'SHIELD count: {len(shield)}')
    print(f'SNIPER count: {len(sniper)}')
except Exception as e:
    print('Error:', e)
