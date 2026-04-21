import os

path = r'c:\github\cobalt-multi-agent\backend\src\tools\scanner.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace('"gap_max": 15.0,', '"gap_max": 500.0,')
content = content.replace('"gap_min": 1.5,', '"gap_min": -20.0,')
content = content.replace('"rvol_veto_max": 5.0,', '"rvol_veto_max": 100.0,')

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print("Safely neutralized intraday guardrails!")
