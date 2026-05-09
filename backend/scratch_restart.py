import requests
try:
    res = requests.post('http://127.0.0.1:8000/api/system/restart')
    print('Restarted:', res.status_code)
except Exception as e:
    print('Error:', e)
