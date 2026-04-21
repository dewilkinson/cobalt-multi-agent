import os

path = r'c:\github\cobalt-multi-agent\backend\src\tools\smc.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = 'status = "**[PASS]**" if sweep_aligned and tactical_ready else "**[FAIL]**"'
repl = 'status = "**[PASS]**" if macro_bias == "Bullish" and tactical_ready else "**[FAIL]**"'

if target in content:
    content = content.replace(target, repl)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched Apex Authorization Matrix!")
else:
    print("Target string not found.")
