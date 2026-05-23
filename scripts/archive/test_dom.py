import re
try:
    with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
        text = f.read()
    times = list(re.finditer(r'\b\d{1,2}:\d{2}\s(?:AM|PM|am|pm)\b', text))
    print('Found', len(times), 'times')
    for m in times[:5]:
        print('Time:', m.group())
except Exception as e:
    print('Error:', e)
