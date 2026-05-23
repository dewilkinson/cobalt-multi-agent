import json
import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('div', class_=lambda c: c and 'gridrow' in [cls.lower() for cls in c])

extracted_set = set()
extracted = []
last_symbol = None

for row in rows:
    row_text = row.get_text(separator=' ', strip=True)
    
    syms = re.findall(r'\(([A-Z]{1,5})\)|Symbol ([A-Z]{1,5})\b', row_text)
    symbols = [s[0] or s[1] for s in syms if s[0] or s[1]]
    if symbols:
        last_symbol = symbols[-1]
        
    times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', row_text)
    
    if times and last_symbol:
        t = times[-1]
        sig = f"{last_symbol}_{t}"
        if sig not in extracted_set:
            extracted_set.add(sig)
            extracted.append({'symbol': last_symbol, 'time': t})
            print(f"Extracted: {last_symbol} @ {t}")

print(f"Total extracted: {len(extracted)}")

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json', 'r', encoding='utf-8') as f:
    cache = json.load(f)

merged_count = 0
for account_id, activities in cache.items():
    for act in activities:
        snap_time = act.get('trade_date', '') or act.get('time_placed', '')
        snap_sym = ''
        if 'symbol' in act and act['symbol'] and isinstance(act['symbol'], dict) and 'symbol' in act['symbol']:
            snap_sym = act['symbol']['symbol']
            
        if snap_sym and (snap_time.endswith('00:00:00Z') or snap_time.endswith('04:00:00Z') or snap_time.endswith('05:00:00Z')):
            for ex in extracted:
                if ex['symbol'] == snap_sym:
                    merged_count += 1
                    extracted.remove(ex)
                    break

print(f"Merged count: {merged_count}")
