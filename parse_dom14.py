import re
import json

with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

# Look for generic JSON-like structures that contain 'SNDK' or 'BOUGHT'
matches = re.findall(r'\{[^}]*?SNDK[^}]*?\}', text)
for i, m in enumerate(matches[:5]):
    print(f'Match {i}: {m[:200]}')
    
# Let's search for script tags containing SNDK
import bs4
soup = bs4.BeautifulSoup(text, 'html.parser')
for script in soup.find_all('script'):
    if script.string and 'SNDK' in script.string:
        print("FOUND JSON SCRIPT!")
        print(script.string[:500])
