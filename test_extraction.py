import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

soup = BeautifulSoup(text, 'html.parser')

# Find all potential rows. Often it's a div with 'grid' or 'row' or an 'activity' container.
# Let's find all <activity-order-history-row> or something similar.
# In Angular it might be <app-activity-row> or something.
# We can just iterate over all divs that have a substantial amount of text.

rows = soup.find_all('div', class_=lambda c: c and 'row' in c.lower())
print(f"Found {len(rows)} div rows")

extracted = []
for row in rows:
    row_text = row.get_text(separator=' ', strip=True)
    
    times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', row_text)
    symbols = re.findall(r'\(([A-Z]{1,5})\)', row_text)
    
    if times and symbols:
        ex = {'symbol': symbols[-1], 'time': times[-1]}
        if ex not in extracted:
            extracted.append(ex)
            print(f"Extracted: {ex['symbol']} at {ex['time']}")
            
print(f"Total unique extracted: {len(extracted)}")
