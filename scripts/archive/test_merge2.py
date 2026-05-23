import json
import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('div', class_=lambda c: c and 'row' in c.lower())

extracted_set = set()
extracted = []
for row in rows:
    row_text = row.get_text(separator=' ', strip=True)
    times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', row_text)
    symbols = re.findall(r'Symbol ([A-Z]{1,5})\b', row_text)
    
    if times and symbols:
        sym = symbols[-1]
        t = times[-1]
        sig = f"{sym}_{t}"
        if sig not in extracted_set:
            extracted_set.add(sig)
            extracted.append({'symbol': sym, 'time': t})

print(f"Extracted trades: {extracted}")

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

for account_id, activities in cache.items():
    for act in activities:
        snap_time = act.get('trade_date', '') or act.get('time_placed', '')
        snap_sym = ''
        if 'symbol' in act and act['symbol'] and isinstance(act['symbol'], dict) and 'symbol' in act['symbol']:
            snap_sym = act['symbol']['symbol']
            
        if snap_sym in [e['symbol'] for e in extracted]:
            print(f"CACHE HAS {snap_sym} at {snap_time}")
            
