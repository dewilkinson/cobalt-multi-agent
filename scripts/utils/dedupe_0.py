import json
cache_file = r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\data\brokerage_cache.json'
with open(cache_file, 'r') as f: data = json.load(f)
for acct, acct_data in data.items():
    if not isinstance(acct_data, dict): continue
    activities = acct_data.get('activities', [])
    atp_acts = [a for a in activities if a.get('id', '').startswith('ATP-')]
    hist_acts = [a for a in activities if a.get('id', '').startswith('HIST-')]
    other_acts = [a for a in activities if not a.get('id', '').startswith('ATP-') and not a.get('id', '').startswith('HIST-')]
    atp_lookup = {f"{a.get('symbol', {}).get('symbol', '')}_{a.get('trade_date', '')[:10]}_{a.get('units', 0)}_{a.get('type', '')}": a for a in atp_acts}
    kept_hist = [h for h in hist_acts if f"{h.get('symbol', {}).get('symbol', '')}_{h.get('trade_date', '')[:10]}_{h.get('units', 0)}_{h.get('type', '')}" not in atp_lookup]
    final_acts = atp_acts + kept_hist + other_acts
    final_acts.sort(key=lambda x: x.get('trade_date', ''), reverse=True)
    acct_data['activities'] = final_acts
    print(f'Account {acct}: Kept {len(atp_acts)} ATP, {len(kept_hist)} HIST. Removed {len(hist_acts) - len(kept_hist)} redundant HIST.')
with open(cache_file, 'w') as f: json.dump(data, f, indent=2)
print('Cache deduplicated!')
