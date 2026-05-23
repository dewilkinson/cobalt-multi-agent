import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
divs = soup.find_all('div', class_=lambda c: c and 'expandCollapseIcon' in c)

for i, div in enumerate(divs[:2]):
    print(f"--- Div {i} ---")
    current = div
    for depth in range(5):
        if not current:
            break
        print(f"Level {depth}: <{current.name} class='{current.get('class', [])}'>")
        if current.name != 'div':
            print(f"   Attributes: {current.attrs}")
        current = current.parent
