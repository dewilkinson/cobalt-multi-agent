import sys
import os
os.chdir('backend')
sys.path.append(os.getcwd())
from src.server.app import app
from fastapi.testclient import TestClient

client = TestClient(app)
res = client.get('/api/brokerage/accounts')
print(res.status_code)
print(res.text)
