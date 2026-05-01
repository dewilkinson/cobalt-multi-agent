import json
with open('c:/github/cobalt-multi-agent/scripts/order_history_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines[460:520]):
    if 'symbol' in line.lower() or 'ticker' in line.lower():
        print(f'{i+460}: {line.strip()}')
