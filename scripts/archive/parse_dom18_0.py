import re
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()

times = list(re.finditer(r'\b\d{1,2}:\d{2}\s(?:AM|PM|am|pm)\b', text))
print('Found', len(times), 'times')
for m in times[:25]:
    idx = m.start()
    # Look backwards 2000 chars
    context = text[max(0, idx-2000):idx]
    # Find the last symbol e.g. (SNDK) or (AAPL)
    sym_match = list(re.finditer(r'\(([A-Z]{1,5})\)', context))
    if sym_match:
        print('Time:', m.group(), 'Symbol:', sym_match[-1].group(1))
    else:
        print('Time:', m.group(), 'Symbol: NOT FOUND')
