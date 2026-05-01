import os, json
VAULT_ROOT = r'C:\github\obsidian-vault'
scanner_bucket_path = os.path.join(VAULT_ROOT, '_cobalt', '01_Transit', 'Buckets', 'SCANNER_RES_state.json')

scanner_res_content = {'candidates': []}
if os.path.exists(scanner_bucket_path):
    with open(scanner_bucket_path, encoding='utf-8') as f:
        cands = json.load(f)
        if isinstance(cands, dict): cands = cands.get('candidates', [])
        for c in cands:
            if 'tier' not in c: c['tier'] = 'SWORD'
        scanner_res_content['candidates'].extend(cands)

seen_symbols = set()
deduped_cands = []
for cand in scanner_res_content.get('candidates', []):
    sym = cand.get('symbol', '').upper()
    if sym and sym not in seen_symbols:
        seen_symbols.add(sym)
        deduped_cands.append(cand)
scanner_res_content['candidates'] = deduped_cands

syms = [c.get('symbol') for c in scanner_res_content['candidates']]
import collections
print('Total:', len(syms), 'Unique:', len(set(syms)))
print('Duplicates:', [item for item, count in collections.Counter(syms).items() if count > 1])
print('Symbols:', syms)
