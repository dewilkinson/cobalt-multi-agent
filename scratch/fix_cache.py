import json
p = 'C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json'
with open(p, 'r') as f:
    d = json.load(f)
removed = False
for act_id, acc_data in d.items():
    acts = acc_data.get('activities', [])
    new_acts = []
    for a in acts:
        sym_obj = a.get('symbol', {})
        sym = sym_obj.get('symbol', '') if isinstance(sym_obj, dict) else sym_obj
        if sym == 'NYC' and a.get('price') == 0.0 and '2026-05-12T12:10:54' in str(a.get('trade_date', a.get('time_placed', ''))):
            removed = True
            continue
        new_acts.append(a)
    acc_data['activities'] = new_acts

if removed:
    with open(p, 'w') as f:
        json.dump(d, f, indent=2)
    print('Corrupted $0.00 NYC execution removed successfully.')
else:
    print('Execution not found.')
