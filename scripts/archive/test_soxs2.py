import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('div', class_=lambda c: c and ('gridrow' in c.lower() or 'ao-row-container' in c.lower()))

for row in rows:
    row_text = row.get_text(separator=' ', strip=True)
    if 'SOXS' in row_text:
        times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', row_text)
        print(f"SOXS row times: {times}")
