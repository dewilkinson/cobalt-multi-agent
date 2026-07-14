import os
import json
from datetime import datetime, timezone, timedelta
from zoneinfo import ZoneInfo

def parse_time(act):
    t_str = act.get('trade_date', '') or act.get('time_placed', '')
    eastern_tz = ZoneInfo("America/New_York")
    if not t_str:
        return datetime.min.replace(tzinfo=eastern_tz)
    
    # Strip Z or timezone offset if present, to treat the hours as Eastern Time
    t_str_clean = t_str
    if t_str_clean.endswith('Z'):
        t_str_clean = t_str_clean[:-1]
    if '+' in t_str_clean:
        t_str_clean = t_str_clean.split('+')[0]
        
    # Try parsing Month-Day-Year (e.g. Oct-7-2025 or May-20-2026)
    if '-' in t_str_clean and not t_str_clean.startswith('20'):
        try:
            dt = datetime.strptime(t_str_clean, "%b-%d-%Y")
            return dt.replace(tzinfo=eastern_tz)
        except Exception:
            pass
            
    # Try parsing Month/Day/Year (e.g. 10/7/2025)
    if '/' in t_str_clean:
        try:
            dt = datetime.strptime(t_str_clean, "%m/%d/%Y")
            return dt.replace(tzinfo=eastern_tz)
        except Exception:
            try:
                dt = datetime.strptime(t_str_clean, "%m/%d/%y")
                return dt.replace(tzinfo=eastern_tz)
            except Exception:
                pass
                
    try:
        if 'T' in t_str_clean:
            if '.' in t_str_clean:
                parts = t_str_clean.split('.')
                frac = parts[1][:3]
                t_str_clean = parts[0] + '.' + frac
                dt = datetime.strptime(t_str_clean, "%Y-%m-%dT%H:%M:%S.%f")
            else:
                dt = datetime.strptime(t_str_clean, "%Y-%m-%dT%H:%M:%S")
        else:
            dt = datetime.fromisoformat(t_str_clean)
            
        return dt.replace(tzinfo=eastern_tz)
    except Exception:
        try:
            dt = datetime.fromisoformat(t_str.replace('Z', '+00:00'))
            return dt.astimezone(eastern_tz)
        except Exception:
            return datetime.min.replace(tzinfo=eastern_tz)

def format_price(val):
    val_float = float(val)
    if val_float.is_integer():
        return f"{val_float:.2f}"
    str_val = f"{val_float:.4f}"
    if str_val.endswith("00"):
        return f"{val_float:.2f}"
    return str_val.rstrip('0').rstrip('.') if '.' in str_val else str_val

def main():
    import sys
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
    sys.path.append(os.path.abspath(os.path.join(project_root, "backend")))
    
    cache_file = os.path.join(project_root, "backend", "data", "brokerage_cache.json")
    backup_file = os.path.join(project_root, "backend", "data", "archive", "BrokerageCacheDailyBackup.json")
    
    # Read cache
    if os.path.exists(cache_file):
        with open(cache_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    elif os.path.exists(backup_file):
        with open(backup_file, 'r', encoding='utf-8') as f:
            data = json.load(f)
    else:
        print("Error: No brokerage cache found.")
        return
        
    active_accounts = ["Rollover IRA *5513"]
    try:
        from src.config.loader import get_config
        config = get_config()
        if "DROPZONE_ACCOUNTS" in config:
            active_accounts = list(config["DROPZONE_ACCOUNTS"].keys())
    except Exception as e:
        print(f"Warning: Could not load configuration for active accounts: {e}")
        active_accounts = list(data.keys())

    executions_by_symbol = {}
    closed_trades = []
    
    for account in active_accounts:
        if account not in data:
            continue
            
        activities = data.get(account, {}).get("activities", [])
        if not activities:
            continue
            
        print(f"Generating TradingView Plotter data for account: {account} ({len(activities)} activities)...")
        chronological_acts = sorted(activities, key=parse_time)
        
        # Cutoff date (1st day of the current month)
        eastern_tz = ZoneInfo("America/New_York")
        now = datetime.now(eastern_tz)
        cutoff_date = datetime(now.year, now.month, 1, tzinfo=eastern_tz)
        cleared_orphans = False
        
        tax_lots = {}  # symbol -> {"type": "flat"|"long"|"short", "lots": list}
        
        for act in chronological_acts:
            trade_time = parse_time(act)
            if not cleared_orphans and trade_time >= cutoff_date:
                tax_lots.clear()
                cleared_orphans = True
                
            action = act.get('type', act.get('action', '')).upper()
            status = act.get('status', '').upper()
            if status not in ['EXECUTED', 'FILLED']:
                continue
                
            sym = act.get('symbol', {}).get('symbol') if isinstance(act.get('symbol'), dict) else act.get('symbol')
            if not sym:
                continue
            sym = sym.upper()
            
            qty = float(act.get('units', 0))
            price = float(act.get('price', 0))
            
            time_str_tooltip = trade_time.strftime("%Y-%m-%d %H:%M:%S") + " ET"
            
            if trade_time.year > 1:
                trade_time_adjusted = trade_time - timedelta(minutes=1)
            else:
                trade_time_adjusted = trade_time
            trade_time_truncated = trade_time_adjusted.replace(second=0, microsecond=0)
            time_ms = int(trade_time_truncated.timestamp() * 1000)
            
            if sym not in executions_by_symbol:
                executions_by_symbol[sym] = []
            
            is_buy = action in ["BUY", "BOUGHT", "BTO", "BTC"]
            executions_by_symbol[sym].append({
                "time_ms": time_ms,
                "price": price,
                "qty": qty,
                "is_buy": is_buy,
                "time_str": time_str_tooltip,
                "account": account
            })
            
            if sym not in tax_lots:
                tax_lots[sym] = {"type": "flat", "lots": []}
                
            lot_info = tax_lots[sym]
            
            if is_buy:
                if lot_info["type"] in ["flat", "long"]:
                    lot_info["lots"].append({"qty": qty, "price": price, "time_ms": time_ms})
                    lot_info["type"] = "long"
                else: # cover short
                    buy_qty_remaining = qty
                    while buy_qty_remaining > 0.0001 and len(lot_info["lots"]) > 0:
                        lot = lot_info["lots"][0]
                        match_qty = min(lot["qty"], buy_qty_remaining)
                        # Short PnL = (entry_price - cover_price) * qty
                        pnl = (lot["price"] - price) * match_qty
                        closed_trades.append({
                            "symbol": sym,
                            "open_time_ms": lot["time_ms"],
                            "close_time_ms": time_ms,
                            "open_price": lot["price"],
                            "close_price": price,
                            "qty": match_qty,
                            "pnl": pnl,
                            "account": account
                        })
                        buy_qty_remaining -= match_qty
                        lot["qty"] -= match_qty
                        if lot["qty"] <= 0.0001:
                            lot_info["lots"].pop(0)
                    if buy_qty_remaining > 0.0001:
                        lot_info["lots"].append({"qty": buy_qty_remaining, "price": price, "time_ms": time_ms})
                        lot_info["type"] = "long"
                    elif len(lot_info["lots"]) == 0:
                        lot_info["type"] = "flat"
            else:
                if lot_info["type"] in ["flat", "short"]:
                    lot_info["lots"].append({"qty": qty, "price": price, "time_ms": time_ms})
                    lot_info["type"] = "short"
                else: # close long
                    sell_qty_remaining = qty
                    while sell_qty_remaining > 0.0001 and len(lot_info["lots"]) > 0:
                        lot = lot_info["lots"][0]
                        match_qty = min(lot["qty"], sell_qty_remaining)
                        # Long PnL = (sell_price - buy_price) * qty
                        pnl = (price - lot["price"]) * match_qty
                        closed_trades.append({
                            "symbol": sym,
                            "open_time_ms": lot["time_ms"],
                            "close_time_ms": time_ms,
                            "open_price": lot["price"],
                            "close_price": price,
                            "qty": match_qty,
                            "pnl": pnl,
                            "account": account
                        })
                        sell_qty_remaining -= match_qty
                        lot["qty"] -= match_qty
                        if lot["qty"] <= 0.0001:
                            lot_info["lots"].pop(0)
                    if sell_qty_remaining > 0.0001:
                        lot_info["lots"].append({"qty": sell_qty_remaining, "price": price, "time_ms": time_ms})
                        lot_info["type"] = "short"
                    elif len(lot_info["lots"]) == 0:
                        lot_info["type"] = "flat"

    # Get 7-day cutoff in UTC
    cutoff_time = datetime.now(timezone.utc) - timedelta(days=7)
    cutoff_ms = int(cutoff_time.timestamp() * 1000)
    
    # Filter executions to last 7 days
    recent_executions_by_symbol = {}
    for sym, execs in executions_by_symbol.items():
        recent = [ex for ex in execs if ex["time_ms"] >= cutoff_ms]
        if recent:
            recent_executions_by_symbol[sym] = recent
            
    # Filter closed trades to last 7 days
    recent_closed_by_symbol = {}
    for t in closed_trades:
        if t["close_time_ms"] >= cutoff_ms:
            sym = t["symbol"]
            if sym not in recent_closed_by_symbol:
                recent_closed_by_symbol[sym] = []
            recent_closed_by_symbol[sym].append(t)
        
    # Find the date range of executions actually plotted
    all_timestamps = []
    for sym, execs in recent_executions_by_symbol.items():
        for ex in execs:
            all_timestamps.append(ex["time_ms"])
            
    for sym, trades in recent_closed_by_symbol.items():
        for t in trades:
            all_timestamps.append(t["open_time_ms"])
            all_timestamps.append(t["close_time_ms"])
            
    eastern_tz = ZoneInfo("America/New_York")
    if all_timestamps:
        min_time = datetime.fromtimestamp(min(all_timestamps) / 1000, tz=eastern_tz)
        max_time = datetime.fromtimestamp(max(all_timestamps) / 1000, tz=eastern_tz)
        date_range_str = f" ({min_time.strftime('%Y-%m-%d')} to {max_time.strftime('%Y-%m-%d')})"
    else:
        # Default fallback to last 7 days
        start_date = (datetime.now(eastern_tz) - timedelta(days=7)).strftime('%Y-%m-%d')
        end_date = datetime.now(eastern_tz).strftime('%Y-%m-%d')
        date_range_str = f" ({start_date} to {end_date})"
        
    # Get today's start timestamp in Eastern Time, then get its UTC timestamp
    today_start = datetime.now(eastern_tz).replace(hour=0, minute=0, second=0, microsecond=0)
    today_start_ms = int(today_start.timestamp() * 1000)
    
    # Generate Pine Script
    pine_script = []
    pine_script.append('//@version=6')
    pine_script.append(f'indicator("Daily Trade Plotter{date_range_str}", overlay=true, max_labels_count=500, max_lines_count=500)')
    pine_script.append('')
    pine_script.append('// Inputs')
    pine_script.append('show_labels = input.bool(true, "Show Execution Labels")')
    pine_script.append('show_lines  = input.bool(true, "Show Trade Paths (FIFO)")')
    pine_script.append('only_today  = input.bool(false, "Show Today\'s Trades Only")')
    pine_script.append('')
    pine_script.append('// Helper to draw execution labels')
    pine_script.append('draw_execution(time_ms, price, is_buy, tooltip_val, only_today_flag, today_start_ms) =>')
    pine_script.append('    if show_labels and (not only_today_flag or time_ms >= today_start_ms)')
    pine_script.append('        color_val = is_buy ? color.rgb(0, 200, 83) : color.rgb(139, 0, 0)')
    pine_script.append('        style_val = is_buy ? label.style_label_right : label.style_label_left')
    pine_script.append('        text_val  = is_buy ? "▶" : "◀"')
    pine_script.append('        label.new(x=time_ms, y=price, text=text_val, xloc=xloc.bar_time, color=color_val, textcolor=color.white, style=style_val, size=size.small, tooltip=tooltip_val)')
    pine_script.append('')
    pine_script.append('// Helper to draw trade path lines')
    pine_script.append('draw_trade_line(t1, p1, t2, p2, pnl, only_today_flag, today_start_ms) =>')
    pine_script.append('    if show_lines and (not only_today_flag or t2 >= today_start_ms)')
    pine_script.append('        line_color = pnl >= 0 ? color.rgb(38, 166, 154, 50) : color.rgb(229, 115, 115, 50)')
    pine_script.append('        line.new(x1=t1, y1=p1, x2=t2, y2=p2, xloc=xloc.bar_time, color=line_color, style=line.style_dashed, width=2)')
    pine_script.append('')
    pine_script.append(f'today_start = {today_start_ms} // {today_start.strftime("%Y-%m-%d %H:%M:%S")} UTC')
    pine_script.append('current_sym = syminfo.ticker')
    pine_script.append('')
    # Sort symbols so code is deterministic
    all_symbols = sorted(list(set(list(recent_executions_by_symbol.keys()) + list(recent_closed_by_symbol.keys()))))
    
    for sym in all_symbols:
        clean_sym = sym.lstrip('/')
        cond = f'current_sym == "{sym}" or current_sym == "{clean_sym}"'
        if sym.startswith('/'):
            cond += f' or str.contains(current_sym, "{clean_sym}")'
        pine_script.append(f'if barstate.islast and ({cond})')
        
        # Plot trade lines first
        lines = recent_closed_by_symbol.get(sym, [])
        for ln in lines:
            pine_script.append(f'    draw_trade_line({ln["open_time_ms"]}, {ln["open_price"]}, {ln["close_time_ms"]}, {ln["close_price"]}, {ln["pnl"]}, only_today, today_start)')
            
        execs = recent_executions_by_symbol.get(sym, [])
        for ex in execs:
            is_buy_str = "true" if ex["is_buy"] else "false"
            tooltip_val = f'{"Buy Entry" if ex["is_buy"] else "Sell Exit"}\\nAccount: {ex.get("account", "Unknown")}\\nTime: {ex["time_str"]}\\nQty: {ex["qty"]}\\nPrice: ${format_price(ex["price"])}'
            pine_script.append(f'    draw_execution({ex["time_ms"]}, {ex["price"]}, {is_buy_str}, "{tooltip_val}", only_today, today_start)')
            
    # Output file
    output_dir = os.path.join(project_root, "data", "exports")
    os.makedirs(output_dir, exist_ok=True)
    output_file = os.path.join(output_dir, "tradingview_trades.pine")
    
    with open(output_file, 'w', encoding='utf-8') as f:
        f.write('\n'.join(pine_script))
        
    print(f"Success! Generated Pine Script at {output_file}")
    print(f"Total symbols processed: {len(all_symbols)}")

if __name__ == '__main__':
    main()
