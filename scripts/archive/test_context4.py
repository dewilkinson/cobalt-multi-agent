import re
from bs4 import BeautifulSoup

with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

soup = BeautifulSoup(text, 'html.parser')

# Find all grid rows
rows = soup.find_all(class_='pvd-table__row')
print(f"Found {len(rows)} rows.")
for row in rows:
    # See if it has a symbol and a time
    text_content = row.get_text(separator=' ', strip=True)
    
    # Try to find symbol. Often it's just the 1-5 char uppercase string
    # But usually it's in a specific column. Let's just find the time first.
    times = re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', text_content)
    if times:
        print(f"Row has time: {times[0]}")
        print(f"Row text: {text_content[:200]}...")
