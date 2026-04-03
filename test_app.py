import requests
try:
    res = requests.post('http://localhost:8000/api/vli/action-plan', json={'text': 'analyze amd'})
    print("STATUS:", res.status_code)
    print("CONTENT:", res.text)
except Exception as e:
    print("FATAL ERROR:", e)
