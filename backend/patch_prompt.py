import os

path = r'c:\github\cobalt-multi-agent\backend\src\prompts\risk_manager.md'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = '- If you detect a **"Binary Event"** (e.g. Earnings print or Regulatory announcement) for ANY $\\$20-\\$50$ name, you force a $0\\%$ exposure constraint on that ticker. No exceptions.'
repl = '- If you detect an imminent **"Binary Event"** (e.g. Earnings print or Regulatory announcement occurring on the exact day or the day prior to execution) for ANY $\\$20-\\$50$ name, you force a $0\\%$ exposure constraint on that ticker. Distant events (e.g. earnings next week) pose no swing-trade gap risk and are fully authorized.'

if target in content:
    content = content.replace(target, repl)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched Binary Event risk parameter!")
else:
    print("Target string not found in risk_manager.md")
