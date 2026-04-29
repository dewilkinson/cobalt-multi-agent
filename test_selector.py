import re
with open('c:/github/cobalt-multi-agent/data/fidelity_extension_debug_dom.html', 'r', encoding='utf-8') as f:
    html = f.read()

matches = re.findall(r'pvd-button-group__button--secondary', html)
print(f'Found {len(matches)} secondary buttons')
