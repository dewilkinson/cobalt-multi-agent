import re
with open('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

matches = re.findall(r'pvd-button-group__button--secondary', html)
print(f'Found {len(matches)} secondary buttons')
