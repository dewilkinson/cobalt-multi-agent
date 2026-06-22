import sys, json, os, csv, io
from datetime import datetime

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
account = 'Rollover IRA *5513'

def parse_history(csv_path):
    if not os.path.exists(csv_path): return []
    with open(csv_path, 'r', encoding='utf-8-sig') as f: lines = f.readlines()
    header_idx = next((i for i, l in enumerate(lines) if l.startswith('Description,Symbol')), -1)
    if header_idx == -1: return []
    reader = csv.DictReader(io.StringIO(''.join(lines[header_idx:])))
    acts = []
    for row in reader:
        action_desc = (row.get('Description') or '').upper()
        sym = (row.get('Symbol') or '').upper().strip()
        if not sym or row.get('Account', '').strip() not in account: continue
        if 'BOUGHT' in action_desc: action = 'BUY'
        elif 'SOLD' in action_desc: action = 'SELL'
        else: continue
        
        try:
            qty = abs(float((row.get('Quantity') or '0').replace(',', '').replace('"', '')))
            price = float((row.get('Price') or '0').replace(',', '').replace('"', ''))
            
            date_str = row.get('Settlement Date', '').strip()
            if not date_str or date_str == '--': continue
            dt_obj = datetime.strptime(date_str, '%b-%d-%Y')
        except: continue
        if qty == 0: continue
        
        acts.append({'sym': sym, 'action': action, 'qty': qty, 'price': price, 'date': dt_obj})
    return acts

acts_2025 = parse_history(os.path.join(workspace_dir, 'data/dropzone/archive/Activity_2025.csv'))
acts_2026 = parse_history(os.path.join(workspace_dir, 'data/dropzone/archive/Activity_2026.csv'))
all_acts = acts_2025 + acts_2026

# Sort chronological (oldest first), and Buy before Sell if same day
all_acts.sort(key=lambda x: (x['date'], 0 if x['action'] == 'BUY' else 1))

positions = {}
for act in all_acts:
    sym = act['sym']
    if sym not in positions:
        positions[sym] = 0.0
    if act['action'] == 'BUY':
        positions[sym] += act['qty']
    elif act['action'] == 'SELL':
        # Deduct but do not go below 0
        positions[sym] -= act['qty']

open_pos = {s: q for s, q in positions.items() if abs(q) > 0.0001}
print(f"Total unique symbols: {len(positions)}")
print(f"Open positions in historical CSVs: {len(open_pos)}")
for s, q in sorted(open_pos.items()):
    print(f"  {s}: {q:.4f}")
