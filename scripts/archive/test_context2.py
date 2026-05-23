import re
with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()
times = list(re.finditer(r'\b\d{1,2}:\d{2}:\d{2}\s(?:AM|PM|am|pm)\b', text))
print('Found', len(times), 'times with seconds')
for m in times[:3]:
    idx = m.start()
    context = text[max(0, idx-1000):idx]
    # Check what the symbol format is. Fidelity often has <span ...>AAPL</span>
    sym = list(re.finditer(r'>([A-Z]{1,5})<', context))
    if sym:
        print('Time:', m.group(), 'Symbol:', sym[-1].group(1))
    else:
        print('Time:', m.group(), 'Symbol: Not found')
