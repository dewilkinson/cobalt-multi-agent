import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
buttons = soup.find_all('button', attrs={'aria-expanded': 'false'})

print(f"Found {len(buttons)} buttons with aria-expanded=false")
for i, btn in enumerate(buttons[:5]):
    print(f"Tag: {btn.name}, Class: {btn.get('class')}")
