import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
div = soup.find('div', class_=lambda c: c and 'expandCollapseIcon' in c)

print("--- Icon HTML ---")
print(div.parent.prettify())
