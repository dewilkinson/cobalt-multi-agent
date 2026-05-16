import requests
import json
try:
    res = requests.get('http://127.0.0.1:3000/api/v1/scanner/apex').json()
    grades = [c.get('grade', 'MISSING') for c in res.get('candidates', [])]
    print('Apex:', grades)
except Exception as e:
    print('Error:', e)
