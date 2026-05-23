import re
from bs4 import BeautifulSoup

with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

if re.search(r'expand\s*all', html, re.IGNORECASE):
    print('Found Expand All string!')
else:
    print('No Expand All string')
