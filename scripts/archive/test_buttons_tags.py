import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
buttons = soup.find_all(lambda tag: tag.has_attr('class') and any('expandcollapse' in c.lower() for c in tag['class']))

print(f"Found {len(buttons)} expandcollapse buttons")
for i, btn in enumerate(buttons[:3]):
    print(f'Button {i} Tag: {btn.name}')
