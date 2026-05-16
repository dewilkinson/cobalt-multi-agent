import requests
import json
try:
    res1 = requests.get('http://127.0.0.1:3000/api/v1/scanner/shield').json()
    grades1 = [c.get('grade', 'MISSING') for c in res1.get('candidates', [])]
except Exception as e:
    grades1 = str(e)
try:
    res2 = requests.get('http://127.0.0.1:3000/api/v1/scanner/sniper').json()
    grades2 = [c.get('grade', 'MISSING') for c in res2.get('candidates', [])]
except Exception as e:
    grades2 = str(e)
print('Shield:', grades1)
print('Sniper:', grades2)
