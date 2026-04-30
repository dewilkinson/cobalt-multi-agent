import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

if re.search(r'expand\s*all', html, re.IGNORECASE):
    print('Found Expand All string!')
else:
    print('No Expand All string')
