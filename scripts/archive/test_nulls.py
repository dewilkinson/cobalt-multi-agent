import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
buttons = soup.find_all(lambda tag: tag.has_attr('class') and any('expandcollapse' in c.lower() for c in tag['class']) and tag.get('aria-expanded') is None)

print(f"Found {len(buttons)} expandcollapse elements with aria-expanded=None")
for i, btn in enumerate(buttons[:10]):
    print(f"Tag: {btn.name}, Class: {btn.get('class')}")
