import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

soup = BeautifulSoup(html, 'html.parser')
buttons = soup.find_all(lambda tag: tag.has_attr('aria-label') and 'show info for' in tag['aria-label'].lower())

print(f"Found {len(buttons)} show info elements")
for i, btn in enumerate(buttons[:5]):
    print(f"Tag: {btn.name}, Class: {btn.get('class')}, Aria-label: {btn.get('aria-label')}, aria-expanded: {btn.get('aria-expanded')}")
