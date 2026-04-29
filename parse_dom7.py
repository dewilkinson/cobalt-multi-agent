import re
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()
print('Matches for time formats:', list(set(re.findall(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm|a\.m\.|p\.m\.)\b', text) + re.findall(r'\b\d{1,2}:\d{2}\s(?:AM|PM|am|pm|a\.m\.|p\.m\.)\b', text))))
