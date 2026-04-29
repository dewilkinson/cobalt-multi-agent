import re
with open('data/fidelity_orders_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()
for m in re.finditer(r'\b09:41\s*AM\b', text, re.IGNORECASE):
    idx = m.start()
    print('CONTEXT:')
    print(text[max(0, idx-100):idx+100])
