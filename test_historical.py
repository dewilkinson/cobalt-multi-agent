import json
import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('div', class_=lambda c: c and ('gridrow' in c.lower() or 'ao-row-container' in c.lower()))

extracted_set = set()
extracted = []
for row in rows:
    row_text = row.get_text(separator=' ', strip=True)
    times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', row_text)
    syms = re.findall(r'\(([A-Z]{1,5})\)|Symbol ([A-Z]{1,5})\b', row_text)
    symbols = [s[0] or s[1] for s in syms if s[0] or s[1]]
    
    if times and symbols:
        sym = symbols[-1]
        t = times[-1]
        sig = f"{sym}_{t}"
        if sig not in extracted_set:
            extracted_set.add(sig)
            extracted.append({'symbol': sym, 'time': t})
            print(f"Extracted: {sym} @ {t}")

print(f"Total extracted: {len(extracted)}")
