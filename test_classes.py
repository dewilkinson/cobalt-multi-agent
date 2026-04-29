import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
rows = soup.find_all('div', class_=lambda c: c and ('gridrow' in c.lower() or 'ao-row-container' in c.lower()))
for row in rows[:5]:
    print('Classes:', row.get('class'))
    text = row.get_text(separator=' ', strip=True)
    times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', text)
    print('Len text:', len(text), 'Times:', len(times))
