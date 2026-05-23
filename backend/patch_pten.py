import os

path_scanner = r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend\src\tools\scanner.py'
with open(path_scanner, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace config variables in scanner.py
content = content.replace('"price_min": 10.0,', '"price_min": 5.0,')
content = content.replace('"market_cap_max": 2_000_000_000,', '"market_cap_max": 4_000_000_000,')
content = content.replace('"float_max": 100_000_000,', '"float_max": 400_000_000,')

with open(path_scanner, 'w', encoding='utf-8') as f:
    f.write(content)

path_trawl = r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend\src\tools\sortino_sniper_trawl.py'
with open(path_trawl, 'r', encoding='utf-8') as f:
    content_trawl = f.read()

# Replace filter string in sortino_sniper_trawl.py
target = 'FINVIZ_FILTERS = "f=cap_small,sh_float_u100,sh_price_10to50,ta_perf_13w20o"'
repl = 'FINVIZ_FILTERS = "f=cap_smallover,sh_float_u500,sh_price_5to50,ta_perf_13w20o"'
content_trawl = content_trawl.replace(target, repl)

with open(path_trawl, 'w', encoding='utf-8') as f:
    f.write(content_trawl)

print("Safely replaced scanner constraints for PTEN relaxation.")
