import re
with open('c:/github/cobalt-multi-agent/scripts/order_history_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines[460:510]):
    if 'time' in line.lower() or 'date' in line.lower() or 'parse' in line.lower() or 'strptime' in line.lower():
        print(f'{i+460}: {line.strip()}')
