import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

soup = BeautifulSoup(text, 'html.parser')
rows = soup.find_all('div', class_=lambda c: c and 'row' in c.lower())

for row in rows:
    row_text = row.get_text(separator=' ', strip=True)
    times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', row_text)
    if times and len(row_text) > 50 and len(row_text) < 1000:
        print(f"Time: {times[0]}")
        print(f"Row Text: {row_text}")
        print("-" * 50)
        break
