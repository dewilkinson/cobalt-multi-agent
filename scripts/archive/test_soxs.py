from bs4 import BeautifulSoup
with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()
soup = BeautifulSoup(text, 'html.parser')
for row in soup.find_all('div', class_=lambda c: c and 'row' in c.lower()):
    t = row.get_text(separator=' ', strip=True)
    if 'SOXS' in t:
        print('SOXS row:', t[:100])
