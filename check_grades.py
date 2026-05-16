import json, os
from collections import Counter

files = [
    'c:/github/cobalt-multi-agent/backend/data/STRIKE_LIST.json',
    'c:/github/obsidian-vault/_cobalt/01_Transit/Buckets/SCANNER_RES_state.json',
    'c:/github/obsidian-vault/_cobalt/01_Transit/Buckets/STRIKE_RES_state.json'
]

for f in files:
    if os.path.exists(f):
        data = json.load(open(f, encoding='utf-8'))
        candidates = data.get('candidates', []) or data.get('strike_list', [])
        grades = [c.get('grade', 'MISSING') for c in candidates]
        print(f'{os.path.basename(f)}: {Counter(grades)}')
