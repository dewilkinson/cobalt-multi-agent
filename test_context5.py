import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

soup = BeautifulSoup(text, 'html.parser')

rows = soup.find_all(class_='pvd-table__row')
last_symbol = None

for row in rows:
    text_content = row.get_text(separator=' ', strip=True)
    
    # Check if this row has a symbol format like YOU BOUGHT (SNDK) or YOU SOLD (AAPL)
    # Actually let's just look for (SYMBOL)
    sym_match = re.search(r'\(([A-Z]{1,5})\)', text_content)
    if sym_match:
        last_symbol = sym_match.group(1)
        
    times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', text_content)
    if times and last_symbol:
        print(f"Extracted: {last_symbol} at {times[0]}")
