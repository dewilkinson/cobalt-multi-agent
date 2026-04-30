
import requests

url = 'http://127.0.0.1:8000/api/vli/action-plan'
payload = {
    'text': 'show cpt report',
    'direct_mode': False,
    'raw_data_mode': False,
    'background_synthesis': False
}
try:
    response = requests.post(url, json=payload, timeout=60)
    print(response.json())
except Exception as e:
    print('Error:', e)

