import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
buttons = soup.find_all(lambda tag: tag.has_attr('class') and any('expandcollapse' in c.lower() for c in tag['class']))

print(f"Found {len(buttons)} expandcollapse buttons")
for i, btn in enumerate(buttons[:3]):
    print(f'Button {i}:')
    print('  Text:', repr(btn.text))
    print('  Aria-label:', btn.get('aria-label'))
    print('  pvd-aria-label:', btn.get('pvd-aria-label'))
    print('  aria-expanded:', btn.get('aria-expanded'))
    print('  pvd-aria-expanded:', btn.get('pvd-aria-expanded'))
