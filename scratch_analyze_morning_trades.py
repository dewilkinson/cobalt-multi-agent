import sys
import json
import re
from datetime import datetime
from collections import defaultdict
import statistics

sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache

d = BrokerageCache._load_cache()
acts = d.get('Rollover IRA *5513', {}).get('activities', [])

def extract_hour(date_str):
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.hour
    except:
        m = re.search(r'T(\d{2}):', date_str)
        if m: return int(m.group(1))
    return -1

for act in acts:
    date_str = act.get('trade_date', act.get('time_placed', ''))
    act['sort_date'] = date_str

acts = sorted(acts, key=lambda a: a.get('sort_date', ''))

tax_lots = {}
trades = []

for act in acts:
    action = act.get('type', act.get('action', 'N/A')).upper()
    status = str(act.get('status', act.get('state', 'Executed'))).upper()
    if action not in ['BUY', 'SELL', 'BOUGHT', 'SOLD', 'BTO', 'STC', 'BTC', 'STO'] or status in ['OPEN', 'PENDING', 'CANCELED', 'REJECTED']: 
        continue
        
    sym_obj = act.get('symbol') or act.get('universal_symbol') or {}
    sym = sym_obj.get('symbol', act.get('symbol')) if isinstance(sym_obj, dict) else sym_obj
    if not sym: continue
    sym_raw = str(sym).upper().replace('-USD', '').replace('*', '')
    qty = float(act.get('units', 0))
    price = float(act.get('price', 0))
    
    date_str = act.get('time_placed', act.get('trade_date', ''))
    
    if sym_raw not in tax_lots: tax_lots[sym_raw] = []
    
    if action in ['BUY', 'BOUGHT', 'BTO', 'BTC']:
        tax_lots[sym_raw].append({'qty': qty, 'price': price, 'date': date_str})
    elif action in ['SELL', 'SOLD', 'STC', 'STO']:
        sell_qty_remaining = qty
        
        while sell_qty_remaining > 0.0001 and len(tax_lots[sym_raw]) > 0:
            lot = tax_lots[sym_raw][0]
            if lot['qty'] <= sell_qty_remaining:
                pnl = (price - lot['price']) * lot['qty']
                trades.append({
                    'sym': sym_raw,
                    'pnl': pnl,
                    'win': 1 if pnl > 0 else 0,
                    'qty': lot['qty'],
                    'dollar_size': lot['qty'] * lot['price'],
                    'buy_date': lot['date'],
                    'sell_date': date_str,
                    'buy_hour': extract_hour(lot['date']),
                    'sell_hour': extract_hour(date_str),
                })
                sell_qty_remaining -= lot['qty']
                tax_lots[sym_raw].pop(0)
            else:
                pnl = (price - lot['price']) * sell_qty_remaining
                trades.append({
                    'sym': sym_raw,
                    'pnl': pnl,
                    'win': 1 if pnl > 0 else 0,
                    'qty': sell_qty_remaining,
                    'dollar_size': sell_qty_remaining * lot['price'],
                    'buy_date': lot['date'],
                    'sell_date': date_str,
                    'buy_hour': extract_hour(lot['date']),
                    'sell_hour': extract_hour(date_str),
                })
                lot['qty'] -= sell_qty_remaining
                sell_qty_remaining = 0

# Filter for morning trades (opened between 9:00 AM and 10:59 AM)
# Note: sometimes 9 AM is 09 or 9.
morning_trades = [t for t in trades if t['buy_hour'] in [9, 10]]

winners = [t for t in morning_trades if t['win'] == 1]
losers = [t for t in morning_trades if t['win'] == 0]

print(f"Total Morning Trades (Opened 9-10 AM): {len(morning_trades)}")
if not morning_trades:
    sys.exit(0)
print(f"Morning Win Rate: {(len(winners)/len(morning_trades))*100:.1f}%\n")

def analyze_group(group, name):
    if not group: return
    avg_size = sum(t['dollar_size'] for t in group) / len(group)
    
    hold_times = []
    for t in group:
        try:
            b_dt = datetime.fromisoformat(t['buy_date'].replace('Z', '+00:00'))
            s_dt = datetime.fromisoformat(t['sell_date'].replace('Z', '+00:00'))
            hold_times.append((s_dt - b_dt).total_seconds() / 60) # minutes
        except: pass
    
    avg_hold = sum(hold_times)/len(hold_times) if hold_times else 0
    med_hold = statistics.median(hold_times) if hold_times else 0
    
    print(f"--- {name} ({len(group)} trades) ---")
    print(f"  Avg Position Size: ${avg_size:.2f}")
    print(f"  Avg Hold Time    : {avg_hold:.1f} mins (Median: {med_hold:.1f} mins)")
    
    # Tickes
    tickers = defaultdict(int)
    for t in group: tickers[t['sym']] += 1
    top_tickers = sorted(tickers.items(), key=lambda x: x[1], reverse=True)[:5]
    print(f"  Most Traded      : {', '.join([f'{k} ({v})' for k,v in top_tickers])}\n")

analyze_group(winners, "MORNING WINNERS")
analyze_group(losers, "MORNING LOSERS")

# Sizing breakdown for morning trades
print("--- MORNING WIN RATE BY DOLLAR SIZE ---")
buckets = {
    '< $500': lambda x: x < 500,
    '$500-$2000': lambda x: 500 <= x < 2000,
    '> $2000': lambda x: x >= 2000
}
for name, func in buckets.items():
    b_trades = [t for t in morning_trades if func(t['dollar_size'])]
    if not b_trades: continue
    wr = (sum(t['win'] for t in b_trades) / len(b_trades)) * 100
    pnl = sum(t['pnl'] for t in b_trades)
    print(f"  {name:12s}: {len(b_trades):3d} trades | Win Rate: {wr:5.1f}% | PnL: ${pnl:8.2f}")

