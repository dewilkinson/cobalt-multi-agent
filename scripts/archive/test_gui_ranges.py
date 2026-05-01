import re
with open('c:/github/cobalt-multi-agent/scripts/order_history_gui.py', 'r', encoding='utf-8') as f:
    lines = f.readlines()

for i, line in enumerate(lines):
    if 'Past ' in line or 'Week' in line or 'Days' in line or 'range' in line.lower() or 'filter' in line.lower():
        print(f'{i+1}: {line.strip()}')
