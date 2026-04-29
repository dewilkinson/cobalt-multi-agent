import os
import sys
import json

backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "backend"))
if backend_dir not in sys.path:
    sys.path.append(backend_dir)

from src.services.brokerage_cache import BrokerageCache

with open('c:/github/cobalt-multi-agent/data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

payload = {
    'payloadType': 'dom',
    'html': html
}

merged = BrokerageCache.ingest_fidelity_payload(payload)
print(f"Successfully processed historical DOM! Merged {merged} times into the cache.")
