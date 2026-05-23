import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
divs = soup.find_all('div', class_=lambda c: c and 'expandCollapseIcon' in c)

expanded_false = 0
expanded_true = 0
expanded_none = 0

for div in divs:
    val = div.get('aria-expanded')
    if val == 'false':
        expanded_false += 1
    elif val == 'true':
        expanded_true += 1
    else:
        expanded_none += 1

print(f"Total divs: {len(divs)}")
print(f"aria-expanded='false': {expanded_false}")
print(f"aria-expanded='true': {expanded_true}")
print(f"aria-expanded=None: {expanded_none}")
