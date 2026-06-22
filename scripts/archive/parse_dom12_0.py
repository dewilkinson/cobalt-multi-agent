import re
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

matches = list(re.finditer(r'\b\d{1,2}:\d{2}\s(?:AM|PM|am|pm)\b', text))
if matches:
    m = matches[0]
    idx = m.start()
    print("Match:", m.group(0))
    print("Context:", text[max(0, idx-150):idx+150])
