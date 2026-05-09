import sys, json, os, csv, io
sys.path.append('c:/github/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache
import datetime

account = 'Rollover IRA *5513'

def parse_history(csv_path):
    if not os.path.exists(csv_path): return []
    with open(csv_path, 'r', encoding='utf-8-sig') as f: lines = f.readlines()
    header_idx = next((i for i, l in enumerate(lines) if l.startswith('Run Date,Account')), -1)
    if header_idx == -1: return []
    reader = csv.DictReader(io.StringIO(''.join(lines[header_idx:])))
    acts = []
    for row in reader:
        action_desc = (row.get('Action') or '').upper()
        sym = (row.get('Symbol') or '').upper().strip()
        if not sym or row.get('Account', '').strip() not in account: continue
        if 'BOUGHT' in action_desc: action = 'BUY'
        elif 'SOLD' in action_desc: action = 'SELL'
        else: continue  # Filter non-BUY/SELL
        
        try:
            qty = abs(float((row.get('Quantity') or '0').replace(',', '')))
            price = float((row.get('Price ($)') or '0').replace(',', ''))
            dt_obj = datetime.datetime.strptime(row.get('Run Date'), '%m/%d/%Y')
        except: continue
        if qty == 0: continue
        
        acts.append({'sym': sym, 'action': action, 'qty': qty, 'price': price, 'date': dt_obj, 'raw_row': row})
    return acts

acts_2025 = parse_history('c:/github/cobalt-multi-agent/data/dropzone/Activity_2025.csv')
acts_2026 = parse_history('c:/github/cobalt-multi-agent/data/dropzone/Activity_2026.csv')
all_acts = acts_2025 + acts_2026

# Sort chronological (oldest first), and Buy before Sell if same day
all_acts.sort(key=lambda x: (x['date'], 0 if x['action'] == 'BUY' else 1))

inventory = {}
final_activities = []

daily_counters = {}
for act in all_acts:
    sym = act['sym']
    date_str = act['date'].strftime('%Y-%m-%d')
    
    if sym not in inventory: inventory[sym] = 0.0
    
    if act['action'] == 'BUY':
        inventory[sym] += act['qty']
    elif act['action'] == 'SELL':
        if inventory[sym] < 0.0001:
            continue # Skip orphaned sells entirely (No Short Positions)
        if act['qty'] > inventory[sym]:
            act['qty'] = inventory[sym] # Cap to max inventory to prevent going short
        inventory[sym] -= act['qty']
        if act['qty'] < 0.0001: continue
        
    # TradeZella Chronological Timestamp
    if date_str not in daily_counters: daily_counters[date_str] = 1
    seconds = daily_counters[date_str]
    daily_counters[date_str] += 1
    
    time_str = f"{seconds//3600:02d}:{(seconds%3600)//60:02d}:{seconds%60:02d}"
    iso_time = f"{date_str}T09:30:{seconds%60:02d}.000Z" if seconds < 60 else f"{date_str}T09:{(30+seconds//60)%60:02d}:{seconds%60:02d}.000Z"
    
    final_activities.append({
        'id': f"HIST-{sym}-{iso_time}-{act['qty']}-{act['action']}".replace(':', '').replace(' ', '-'),
        'type': act['action'],
        'units': act['qty'],
        'price': act['price'],
        'trade_date': iso_time,
        'status': 'Executed',
        'symbol': {'symbol': sym}
    })

cache = BrokerageCache._load_cache()
cache[account] = {'activities': final_activities, 'positions': [], 'closed_positions': cache.get(account, {}).get('closed_positions', []), 'balances': cache.get(account, {}).get('balances', {})}
BrokerageCache._save_cache(cache)
print(f'Imported {len(final_activities)} chronological activities after filtering.')

