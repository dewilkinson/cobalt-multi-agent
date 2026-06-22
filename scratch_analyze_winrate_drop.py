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

def extract_month(date_str):
    m = re.search(r'(\d{4})-(\d{2})', date_str)
    if m:
        return f"{m.group(1)}-{m.group(2)}"
    try:
        dt = datetime.fromisoformat(date_str.replace('Z', '+00:00'))
        return dt.strftime('%Y-%m')
    except:
        pass
    return "UNKNOWN"

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
    month = extract_month(date_str)
    
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
                    'month': month,
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
                    'month': month,
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
                
        # Skip fallback logic for simpler analysis as it lacks proper buy times

months_to_analyze = ['2026-04', '2026-05', '2026-06']
filtered_trades = [t for t in trades if t['month'] in months_to_analyze]

print("--- WIN RATE BY TIME OF DAY (SELL HOUR) ---")
by_hour = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0.0})
for t in filtered_trades:
    h = t['sell_hour']
    if h != -1:
        by_hour[h]['count'] += 1
        by_hour[h]['wins'] += t['win']
        by_hour[h]['pnl'] += t['pnl']

for h in sorted(by_hour.keys()):
    st = by_hour[h]
    wr = (st['wins']/st['count'])*100
    print(f"Hour {h:02d}: {st['count']:3d} trades | Win Rate: {wr:5.1f}% | PnL: ${st['pnl']:8.2f}")

print("\n--- PERFORMANCE BY DOLLAR SIZING ---")
# Bucket dollar sizing
size_buckets = {
    '< $500': lambda x: x < 500,
    '$500-$2000': lambda x: 500 <= x < 2000,
    '> $2000': lambda x: x >= 2000
}
for month in months_to_analyze:
    print(f"\nMonth: {month}")
    month_trades = [t for t in filtered_trades if t['month'] == month]
    for name, func in size_buckets.items():
        bucket_trades = [t for t in month_trades if func(t['dollar_size'])]
        if not bucket_trades: continue
        wr = (sum(t['win'] for t in bucket_trades) / len(bucket_trades)) * 100
        pnl = sum(t['pnl'] for t in bucket_trades)
        print(f"  {name:12s}: {len(bucket_trades):3d} trades | Win Rate: {wr:5.1f}% | PnL: ${pnl:8.2f}")

print("\n--- HOLD TIMES ---")
for month in months_to_analyze:
    month_trades = [t for t in filtered_trades if t['month'] == month]
    hold_times = []
    for t in month_trades:
        try:
            b_dt = datetime.fromisoformat(t['buy_date'].replace('Z', '+00:00'))
            s_dt = datetime.fromisoformat(t['sell_date'].replace('Z', '+00:00'))
            diff = (s_dt - b_dt).total_seconds() / 3600 # hours
            hold_times.append(diff)
        except:
            pass
    if hold_times:
        avg_hold = sum(hold_times)/len(hold_times)
        med_hold = statistics.median(hold_times)
        print(f"  {month}: Avg Hold = {avg_hold:.1f} hrs | Median Hold = {med_hold:.1f} hrs")

print("\n--- TOP TICKERS (April vs May) ---")
apr_tickers = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0.0})
may_tickers = defaultdict(lambda: {'count': 0, 'wins': 0, 'pnl': 0.0})

for t in filtered_trades:
    if t['month'] == '2026-04':
        apr_tickers[t['sym']]['count'] += 1
        apr_tickers[t['sym']]['wins'] += t['win']
        apr_tickers[t['sym']]['pnl'] += t['pnl']
    elif t['month'] == '2026-05':
        may_tickers[t['sym']]['count'] += 1
        may_tickers[t['sym']]['wins'] += t['win']
        may_tickers[t['sym']]['pnl'] += t['pnl']

top_apr = sorted(apr_tickers.items(), key=lambda x: x[1]['pnl'], reverse=True)[:5]
print("Top 5 April Tickers by PnL:")
for k, v in top_apr:
    wr = (v['wins']/v['count'])*100
    print(f"  {k:5s}: {v['count']:2d} trades | Win Rate: {wr:5.1f}% | PnL: ${v['pnl']:.2f}")

print("\nHow those same tickers performed in May:")
for k, _ in top_apr:
    if k in may_tickers:
        v = may_tickers[k]
        wr = (v['wins']/v['count'])*100
        print(f"  {k:5s}: {v['count']:2d} trades | Win Rate: {wr:5.1f}% | PnL: ${v['pnl']:.2f}")
    else:
        print(f"  {k:5s}: Not traded in May")
