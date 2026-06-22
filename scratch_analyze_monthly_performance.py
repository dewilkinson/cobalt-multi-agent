import sys
import json
import re
from datetime import datetime
from collections import defaultdict

sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
from src.services.brokerage_cache import BrokerageCache

d = BrokerageCache._load_cache()
acts = d.get('Rollover IRA *5513', {}).get('activities', [])

tax_lots = {}
monthly_stats = defaultdict(lambda: {
    'pnl': 0.0,
    'wins': 0,
    'losses': 0,
    'win_amount': 0.0,
    'loss_amount': 0.0,
    'volume': 0,
    'tickers': defaultdict(float),
    'trade_count': 0
})

def extract_month(date_str):
    # Try YYYY-MM
    m = re.search(r'(\d{4})-(\d{2})', date_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    # Try ISO
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m')
    except:
        pass
    return "UNKNOWN"

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
    
    date_str = act.get('trade_date', act.get('time_placed', ''))
    if not date_str: continue
    month = extract_month(date_str)
    
    # Sort activities by date_str for FIFO
    act['sort_date'] = date_str

acts = sorted(acts, key=lambda a: a.get('sort_date', ''))

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
    
    date_str = act.get('trade_date', act.get('time_placed', ''))
    month = extract_month(date_str)
    
    if sym_raw not in tax_lots: tax_lots[sym_raw] = []
    
    if action in ['BUY', 'BOUGHT', 'BTO', 'BTC']:
        tax_lots[sym_raw].append({'qty': qty, 'price': price, 'date': date_str})
        monthly_stats[month]['volume'] += qty
    elif action in ['SELL', 'SOLD', 'STC', 'STO']:
        sell_qty_remaining = qty
        qty_matched = 0
        trade_pnl = 0.0
        
        monthly_stats[month]['volume'] += qty
        
        while sell_qty_remaining > 0.0001 and len(tax_lots[sym_raw]) > 0:
            lot = tax_lots[sym_raw][0]
            if lot['qty'] <= sell_qty_remaining:
                pnl = (price - lot['price']) * lot['qty']
                trade_pnl += pnl
                sell_qty_remaining -= lot['qty']
                qty_matched += lot['qty']
                tax_lots[sym_raw].pop(0)
            else:
                pnl = (price - lot['price']) * sell_qty_remaining
                trade_pnl += pnl
                lot['qty'] -= sell_qty_remaining
                qty_matched += sell_qty_remaining
                sell_qty_remaining = 0
                
        if sell_qty_remaining > 0.0001:
            fallback = 0.0
            for p in d.get('Rollover IRA *5513', {}).get('positions', []):
                if p.get('symbol') == sym_raw:
                    fallback = float(p.get('average_cost') or 0.0)
                    break
            if fallback > 0:
                trade_pnl += (price - fallback) * sell_qty_remaining
                qty_matched += sell_qty_remaining
                sell_qty_remaining = 0
        
        if qty_matched > 0:
            monthly_stats[month]['pnl'] += trade_pnl
            monthly_stats[month]['trade_count'] += 1
            monthly_stats[month]['tickers'][sym_raw] += trade_pnl
            if trade_pnl > 0:
                monthly_stats[month]['wins'] += 1
                monthly_stats[month]['win_amount'] += trade_pnl
            else:
                monthly_stats[month]['losses'] += 1
                monthly_stats[month]['loss_amount'] += trade_pnl

print("Monthly Performance Analysis:")
print("-" * 50)
for m in sorted(monthly_stats.keys()):
    st = monthly_stats[m]
    win_rate = (st['wins'] / st['trade_count']) * 100 if st['trade_count'] > 0 else 0
    avg_win = st['win_amount'] / st['wins'] if st['wins'] > 0 else 0
    avg_loss = st['loss_amount'] / st['losses'] if st['losses'] > 0 else 0
    
    top_tickers = sorted(st['tickers'].items(), key=lambda x: x[1], reverse=True)[:3]
    bottom_tickers = sorted(st['tickers'].items(), key=lambda x: x[1])[:3]
    
    print(f"Month: {m}")
    print(f"  Realized PnL : ${st['pnl']:.2f}")
    print(f"  Trades       : {st['trade_count']} (Wins: {st['wins']}, Losses: {st['losses']})")
    print(f"  Win Rate     : {win_rate:.1f}%")
    print(f"  Avg Winner   : ${avg_win:.2f}")
    print(f"  Avg Loser    : ${avg_loss:.2f}")
    print(f"  Volume       : {st['volume']:,.0f} shares")
    print(f"  Top Tickers  : {', '.join([f'{k} (${v:.0f})' for k,v in top_tickers])}")
    print(f"  Bot Tickers  : {', '.join([f'{k} (${v:.0f})' for k,v in bottom_tickers])}")
    print("-" * 50)
