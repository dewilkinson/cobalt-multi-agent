import os

path = r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend\src\tools\indicators.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = 'async def get_volume_profile(ticker: str, period: str = "60d", interval: str = "1d") -> str:'
repl = 'async def get_volume_profile(ticker: str, period: str = "5d", interval: str = "5m") -> str:'

if target in content:
    content = content.replace(target, repl)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched get_volume_profile time horizon!")
else:
    print("Target string not found.")
