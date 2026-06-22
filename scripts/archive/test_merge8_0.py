import json
import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
# Use re.compile to match classes reliably
rows = soup.find_all(class_=re.compile(r'gridRow', re.I))

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
