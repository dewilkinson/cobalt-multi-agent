import os
import re

debug_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "data", "fidelity_orders_dom.html"))
with open(debug_path, 'r', encoding='utf-8') as f:
    html = f.read()

# Find times like 09:30 AM, 9:30 AM, 14:30:00, etc.
times = re.findall(r'\b\d{1,2}:\d{2}(?::\d{2})?\s*(?:AM|PM|am|pm)?\b', html)
print(f"Generic times found: {len(times)}")
print(list(set(times))[:30])
