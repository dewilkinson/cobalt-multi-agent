import re
with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    text = f.read()
times = list(re.finditer(r'\b\d{1,2}:\d{2}\s(?:AM|PM|am|pm)\b', text))
for m in times[:5]:
    idx = m.start()
    print('Context:', repr(text[idx-50:idx+50]))
