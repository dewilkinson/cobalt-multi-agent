import argparse
import csv
import glob
import io
import os
from collections import defaultdict
from datetime import datetime

def generate_tradezella_csv(input_filename, output_filename, target_month=None, intraday_only=False, week_only=False, today_only=False, date_range=None, reconcile=False, args_ytd=False):
    """
    Converts a full-year Fidelity Account History to a TradeZella Generic CSV.
    Fixes chronological errors by reversing Fidelity's newest-to-oldest order 
    and assigning incremental morning-to-afternoon timestamps.
    """
    if not os.path.exists(input_filename):
        print(f"Error: {input_filename} not found. Ensure the file is in the same folder.")
        return

    # TradeZella Generic Format Headers
    tz_headers = ["Date&Time", "Date", "Time", "Symbol", "Buy/Sell", "Quantity", "Price", "Spread", "Expiration", "Strike", "Call/Put", "Commission", "Fees"]

    # 1. Load the raw data
    with open(input_filename, 'r', encoding='utf-8') as f:
        lines = f.readlines()

    # Find the header row (skipping leading Fidelity metadata)
    header_row_index = -1
    
    # Fiercely strict header mapping targeting Fidelity 'Accounts_History' exports specifically
    expected_header_fragments = ["Run Date", "Account", "Account Number", "Action", "Symbol", "Description", "Type", "Price ($)", "Quantity"]
    
    for i, line in enumerate(lines):
        # We explicitly enforce all fragments to decisively reject 'Orders' or 'Positions' CSV payloads
        if all(fragment in line for fragment in expected_header_fragments):
            header_row_index = i
            break

    if header_row_index == -1:
        print("Error: Could not find valid Fidelity Accounts_History header row. Ensure this is a History export, not an Orders or Transfers export.")
        return

    # Parse the CSV data
    csv_data = "".join(lines[header_row_index:])
    reader = csv.DictReader(io.StringIO(csv_data))
    
    # 2. Extract actual trades
    all_trades_by_date = defaultdict(list)
    for row in reader:
        action = (row.get('Action') or '').upper()
        if "YOU BOUGHT" in action or "YOU SOLD" in action:
            date_key = row.get('Run Date', '').strip()
            if date_key:
                all_trades_by_date[date_key].append(row)

    # 3. Filter for requested range
    daily_groups = defaultdict(list)
    current_year, current_week, _ = datetime.now().isocalendar()
    current_date = datetime.now().date()
    
    # Helper to parse Fidelity dates consistently
    def to_date_obj(d_str):
        try:
            m, d, y = d_str.split('/')
            return datetime(int(y), int(m), int(d)).date()
        except: return None

    # Group valid dates
    valid_dates = sorted(all_trades_by_date.keys(), key=lambda x: (int(x.split('/')[2]), int(x.split('/')[0]), int(x.split('/')[1])))

    for date_key in valid_dates:
        trade_date = to_date_obj(date_key)
        if not trade_date: continue
        
        # Apply Filters
        if target_month and trade_date.month != target_month: continue
        if today_only and trade_date != current_date: continue
        if week_only:
            t_year, t_week, _ = trade_date.isocalendar()
            if t_year != current_year or t_week != current_week: continue
        
        if date_range:
            start_str, end_str = date_range
            start_date = datetime.strptime(start_str, "%Y-%m-%d").date()
            end_date = datetime.strptime(end_str, "%Y-%m-%d").date()
            if not (start_date <= trade_date <= end_date):
                continue
                
        if args_ytd:
            if trade_date.year != current_year: continue
                
        daily_groups[date_key] = list(all_trades_by_date[date_key])
    
    # 4. Handle Trade Reconciliation (Lookback for orphans)
    effective_start_date = None
    if date_range:
        effective_start_date = datetime.strptime(date_range[0], "%Y-%m-%d").date()
    elif week_only:
        # Calculate start of current week (Monday)
        iso_yr, iso_wk, _ = datetime.now().isocalendar()
        effective_start_date = datetime.fromisocalendar(iso_yr, iso_wk, 1).date()
    elif today_only:
        effective_start_date = current_date
    elif target_month:
        effective_start_date = datetime(current_year, target_month, 1).date()
    elif args_ytd:
        effective_start_date = datetime(current_year, 1, 1).date()

    # 5. Sort dates chronologically (Oldest first)
    def parse_date(d_str):
        m, d, y = d_str.split('/')
        return (int(y), int(m), int(d))

    sorted_dates = sorted(daily_groups.keys(), key=parse_date)
    
    final_rows = []
    error_logs = []
    global_balances = __import__('collections').defaultdict(float)
    
    for date_str in sorted_dates:
        # --- INTELLIGENT IRA-SAFE SEQUENCING ---
        # Fidelity exports are inconsistent (sometimes nearest-first, sometimes oldest-first).
        # Since this is an IRA (no shorts), we use a per-symbol heuristic:
        # If the original order makes the position go negative (selling before buying), 
        # but the reversed order stays positive, we use the reversed order.
        
        symbol_trades = defaultdict(list)
        for t in daily_groups[date_str]:
            symbol_trades[t['Symbol'].strip()].append(t)
            
        final_daily_trades = []
        
        for sym, trades_raw in symbol_trades.items():
            # Auto-detect Fidelity intraday chronology by simulating both directions
            # and choosing the sequence that minimizes the IRA short deficit constraint.
            def simulate_deficit(trade_list):
                sim_bal = global_balances[sym]
                max_deficit = 0
                for t in trade_list:
                    q = abs(float(t.get('Quantity', '0').replace(',', '')))
                    if "BOUGHT" in t['Action'].upper(): sim_bal += q
                    else:
                        if sim_bal < q:
                            deficit = q - sim_bal
                            if deficit > max_deficit: max_deficit = deficit
                        sim_bal -= q
                return max_deficit
                
            def_normal = simulate_deficit(trades_raw)
            def_reversed = simulate_deficit(trades_raw[::-1])
            
            # Since Fidelity naturally exports generic dates Newest-First, the file's natural structure 
            # for a given day SHOULD be Newest-First (so we reverse it to achieve Oldest-First).
            # But Fidelity frequently scrambles this and exports Oldest-First.
            # We pick the direction that creates the smallest mathematical IRA violation.
            if def_normal < def_reversed:
                # Top-to-Bottom processing is structurally safer here!
                chronological_trades = trades_raw
            elif def_reversed < def_normal:
                # Bottom-to-Top processing is structurally safer!
                chronological_trades = trades_raw[::-1]
            else:
                # If they tie (e.g. both 0 or both identical deficits), default to assuming the 
                # file segment is consistently Newest-First and needs reversed.
                chronological_trades = trades_raw[::-1]
                
            to_append = []
            for t in chronological_trades:
                q = abs(float(t.get('Quantity', '0').replace(',', '')))
                if "BOUGHT" in t['Action'].upper():
                    global_balances[sym] += q
                    to_append.append((t, q))
                else:
                    # SELL logic
                    if global_balances[sym] >= q - 0.001:
                        global_balances[sym] -= q
                        to_append.append((t, q))
                    else:
                        deficit = q - global_balances[sym]
                        needed = deficit
                        
                        # Look-back
                        # Wait! What if the user sold the stock in January, and now they sell more?
                        # If we just look for Buys without deducting prior Sells, we might reuse Buys!
                        # BUT wait, global_balances ALREADY reflects EVERY trade processed from Jan 1st 
                        # up to this date! So if global_balances[sym] was exactly what was available, 
                        # we don't NEED to look back at all because global_balances ALREADY factored 
                        # in every historical Buy since Jan 1!
                        # The ONLY time we need to look back is if they bought the stock BEFORE 
                        # the effective_start_date (i.e. before Jan 1st)!
                        # Since effective_start_date is --month 4 (April), we need to look back into Jan/Feb/March!
                        
                        if effective_start_date:
                            pre_dates = [dk for dk in valid_dates if to_date_obj(dk) < effective_start_date][::-1]
                            for dk in pre_dates:
                                if needed <= 0.001: break
                                for ht in all_trades_by_date[dk][::-1]:
                                    if ht['Symbol'].strip() == sym and "BOUGHT" in ht['Action'].upper():
                                        hq = abs(float(ht.get('Quantity', '0').replace(',', '')))
                                        take = min(hq, needed)
                                        partial_t = dict(ht)
                                        partial_t['Quantity'] = str(take)
                                        partial_t['_reconciled'] = True
                                        to_append.append((partial_t, take))
                                        global_balances[sym] += take
                                        needed -= take
                                        if needed <= 0.001: break
                        if needed <= 0.001:
                            global_balances[sym] -= q
                            to_append.append((t, q))
                        else:
                            error_logs.append(f"[{date_str}] PRUNED ORPHANED SHORT {sym}: Missing {needed} historic shares to process Sell parameter. Trade discarded.")
                            fulfilled = q - needed
                            if fulfilled > 0.001:
                                global_balances[sym] -= fulfilled
                                partial_sell = dict(t)
                                partial_sell['Quantity'] = str(fulfilled)
                                to_append.append((partial_sell, fulfilled))
            final_daily_trades.extend([t[0] for t in to_append])
        # Sort symbols for deterministic output if desired
        final_daily_trades.sort(key=lambda x: x['Symbol'])

        for i, trade in enumerate(final_daily_trades):

            raw_time = trade.get('Time') or trade.get('Execution Time') or trade.get('Time ($)')
            timestamp = None
            if raw_time:
                timestamp = str(raw_time).strip()
                
            if not timestamp:
                # Assign sequential timestamps starting at market open (09:30:xx)
                # This forces TradeZella to recognize entries before exits for day trades.
                seconds = i + 1
                minutes = seconds // 60
                remaining_secs = seconds % 60
                timestamp = f"09:{30 + minutes:02d}:{remaining_secs:02d}"
            
            action = trade['Action'].upper()
            is_buy = "BOUGHT" in action
            
            # Numeric sanitization
            qty_raw = trade.get('Quantity', '0').replace(',', '')
            qty = abs(float(qty_raw))
            price = trade['Price ($)'].replace('$', '').replace(',', '').strip()
            comm = trade.get('Commission ($)', '0').replace('$', '').strip() or '0'
            fees = trade.get('Fees ($)', '0').replace('$', '').strip() or '0'
            
            # Format date down to MM/DD/YYYY for TradeZella bounds (IRA Long-only context)
            m, d, y = date_str.split('/')
            tz_date = f"{m}/{d}/{y}"
            tz_datetime = f"{tz_date} {timestamp}"
            
            final_rows.append({
                "Date&Time": "",
                "Date": tz_date,
                "Time": timestamp,
                "Symbol": trade['Symbol'].strip(),
                "Buy/Sell": "Buy" if is_buy else "Sell",
                "Quantity": int(qty) if qty.is_integer() else qty,
                "Price": price,
                "Spread": "Stock",
                "Expiration": "",
                "Strike": "",
                "Call/Put": "",
                "Commission": comm,
                "Fees": fees,
                "_reconciled": trade.get('_reconciled', False)
            })

    # 4. Save the full TradeZella-ready file
    os.makedirs(os.path.dirname(output_filename), exist_ok=True)
    with open(output_filename, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers, extrasaction='ignore')
        writer.writeheader()
        writer.writerows(final_rows)
    
    if error_logs:
        error_file = "logs/tradezella-errors.log"
        with open(error_file, 'w', encoding='utf-8') as ef:
            ef.write("\n".join(error_logs))
        print(f"\nWARNING: {len(error_logs)} orphaned short execution(s) were pruned. View {error_file} for details.")
    
    print(f"Success! {len(final_rows)} trades processed into {output_filename}.")
    return final_rows

def launch_audit_dashboard(rows):
    """
    Generates a premium, dark-themed HTML dashboard to audit the processed trades.
    Calculates P&L, ROI, and status based on Long-only logic.
    """
    import tempfile
    import webbrowser
    
    # 1. Summarize Executions into Trades
    trades_by_key = defaultdict(list)
    for r in rows:
        key = (r['Date'], r['Symbol'])
        trades_by_key[key].append(r)
        
    audit_data = []
    # Sort by date descending for the dashboard
    sorted_keys = sorted(trades_by_key.keys(), key=lambda x: datetime.strptime(x[0], "%m/%d/%Y"), reverse=True)
    
    for date, symbol in sorted_keys:
        group = sorted(trades_by_key[(date, symbol)], key=lambda x: x['Time'])
        
        # Calculate Aggregates
        total_buy_qty = sum(float(t['Quantity']) for t in group if t['Buy/Sell'] == 'Buy')
        total_sell_qty = sum(float(t['Quantity']) for t in group if t['Buy/Sell'] == 'Sell')
        
        avg_buy_price = 0
        if total_buy_qty > 0:
            avg_buy_price = sum(float(t['Price']) * float(t['Quantity']) for t in group if t['Buy/Sell'] == 'Buy') / total_buy_qty
            
        avg_sell_price = 0
        if total_sell_qty > 0:
            avg_sell_price = sum(float(t['Price']) * float(t['Quantity']) for t in group if t['Buy/Sell'] == 'Sell') / total_sell_qty
            
        entry_time = group[0]['Time']
        exit_time = group[-1]['Time'] if len(group) > 1 else "-"
        
        # P&L Calculation (Long-only)
        pnl = 0
        roi = 0
        status = "OPEN"
        status_class = "status-open"
        
        if total_buy_qty > 0 and total_sell_qty > 0:
            # We match the minimum of the two for the closed P&L
            closed_qty = min(total_buy_qty, total_sell_qty)
            pnl = (avg_sell_price - avg_buy_price) * closed_qty
            roi = ((avg_sell_price - avg_buy_price) / avg_buy_price) * 100 if avg_buy_price > 0 else 0
            status = "WIN" if pnl > 0 else "LOSS"
            status_class = "status-win" if pnl > 0 else "status-loss"
        elif total_sell_qty > 0:
            status = "CLOSE"
            status_class = "status-close"
        
        audit_data.append({
            "date": date,
            "entry": entry_time,
            "exit": exit_time,
            "symbol": symbol,
            "qty": total_buy_qty if total_buy_qty > 0 else total_sell_qty,
            "pnl": f"${pnl:,.2f}",
            "pnl_val": pnl,
            "entry_p": f"${avg_buy_price:,.2f}" if avg_buy_price > 0 else "-",
            "exit_p": f"${avg_sell_price:,.2f}" if avg_sell_price > 0 else "-",
            "status": status,
            "status_class": status_class,
            "roi": f"{roi:.2f}%" if roi != 0 else "-",
            "is_reconciled": any(t.get('_reconciled', False) for t in group)
        })

    # Extract Date Range for Title
    date_range_str = "All Time"
    if sorted_keys:
        oldest_date = sorted_keys[-1][0]
        newest_date = sorted_keys[0][0]
        if oldest_date == newest_date:
            date_range_str = oldest_date
        else:
            date_range_str = f"{oldest_date} to {newest_date}"
            
    # 2. Build HTML
    html_template = f"""
    <!DOCTYPE html>
    <html lang="en">
    <head>
        <meta charset="UTF-8">
        <title>TradeZella Audit Dashboard ({date_range_str})</title>
        <style>
            :root {{
                --bg: #0d1117;
                --card-bg: rgba(22, 27, 34, 0.8);
                --text: #c9d1d9;
                --text-dim: #8b949e;
                --accent: #58a6ff;
                --success: #238636;
                --danger: #da3633;
                --border: #30363d;
            }}
            body {{
                background-color: var(--bg);
                color: var(--text);
                font-family: 'Segoe UI', Roboto, Helvetica, Arial, sans-serif;
                margin: 0;
                padding: 20px;
                display: flex;
                flex-direction: column;
                align-items: center;
                height: 100vh;
                overflow: hidden;
            }}
            .container {{
                background: var(--card-bg);
                backdrop-filter: blur(10px);
                border: 1px solid var(--border);
                border-radius: 12px;
                width: 95%;
                max-width: 1200px;
                display: flex;
                flex-direction: column;
                max-height: 90vh;
                box-shadow: 0 8px 32px rgba(0,0,0,0.5);
            }}
            .header {{
                padding: 20px;
                border-bottom: 1px solid var(--border);
                display: flex;
                justify-content: space-between;
                align-items: center;
            }}
            .header-text {{
                display: flex;
                flex-direction: column;
            }}
            h2 {{ margin: 0; font-weight: 600; color: #fff; }}
            .subtitle {{ color: #8b949e; font-size: 14px; margin-top: 4px; }}
            .close-btn {{
                background: var(--border);
                color: var(--text);
                border: none;
                padding: 8px 16px;
                border-radius: 6px;
                cursor: pointer;
                transition: 0.2s;
            }}
            .close-btn:hover {{ background: #484f58; }}
            .table-wrapper {{
                overflow-y: auto;
                flex-grow: 1;
                padding: 0 20px;
            }}
            table {{
                width: 100%;
                border-collapse: collapse;
                margin-top: 10px;
            }}
            th {{
                text-align: left;
                padding: 12px;
                color: var(--text-dim);
                font-size: 13px;
                text-transform: uppercase;
                border-bottom: 1px solid var(--border);
                position: sticky;
                top: 0;
                background: #161b22;
                z-index: 10;
            }}
            td {{
                padding: 14px 12px;
                border-bottom: 1px solid #21262d;
                font-size: 14px;
            }}
            tr:hover td {{ background: rgba(88, 166, 255, 0.05); }}
            .symbol {{ font-weight: bold; color: #fff; }}
            .status-pill {{
                padding: 4px 10px;
                border-radius: 20px;
                font-size: 12px;
                font-weight: bold;
                display: inline-block;
            }}
            .status-win {{ background: rgba(35, 134, 54, 0.15); color: #3fb950; border: 1px solid rgba(63, 185, 80, 0.3); }}
            .status-loss {{ background: rgba(218, 54, 51, 0.15); color: #f85149; border: 1px solid rgba(248, 81, 73, 0.3); }}
            .status-open {{ background: rgba(139, 148, 158, 0.15); color: #8b949e; border: 1px solid rgba(139, 148, 158, 0.3); }}
            .status-close {{ background: rgba(88, 166, 255, 0.15); color: #58a6ff; border: 1px solid rgba(88, 166, 255, 0.3); }}
            .status-reconciled {{ background: rgba(255, 191, 0, 0.1); color: #ffbf00; border: 1px solid rgba(255, 191, 0, 0.3); font-size: 10px; vertical-align: middle; margin-left: 8px; }}
            .pnl-pos {{ color: #3fb950; }}
            .pnl-neg {{ color: #f85149; }}
            /* Custom Scrollbar */
            .table-wrapper::-webkit-scrollbar {{ width: 8px; }}
            .table-wrapper::-webkit-scrollbar-track {{ background: transparent; }}
            .table-wrapper::-webkit-scrollbar-thumb {{ background: var(--border); border-radius: 4px; }}
            .table-wrapper::-webkit-scrollbar-thumb:hover {{ background: #484f58; }}
        </style>
    </head>
    <body>
        <div class="container">
            <div class="header">
                <div class="header-text">
                    <h2>📊 Final Audit Dashboard</h2>
                    <div class="subtitle">Range: {date_range_str}</div>
                </div>
                <button class="close-btn" onclick="window.close()">Close Window</button>
            </div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>Date</th>
                            <th>Entry</th>
                            <th>Exit</th>
                            <th>Symbol</th>
                            <th>Quantity</th>
                            <th>Entry Price</th>
                            <th>Exit Price</th>
                            <th>Status</th>
                            <th>P&L</th>
                            <th>ROI</th>
                        </tr>
                    </thead>
                    <tbody>
                        {"".join([f"<tr><td>{row['date']}</td><td>{row['entry']}</td><td>{row['exit']}</td><td class='symbol'>{row['symbol']}{' <span class=\"status-pill status-reconciled\">RECONCILED</span>' if row['is_reconciled'] else ''}</td><td>{row['qty']}</td><td>{row['entry_p']}</td><td>{row['exit_p']}</td><td><span class='status-pill {row['status_class']}'>{row['status']}</span></td><td class='{'pnl-pos' if row['pnl_val'] > 0 else 'pnl-neg' if row['pnl_val'] < 0 else ''}'>{row['pnl']}</td><td class='{'pnl-pos' if row['pnl_val'] > 0 else 'pnl-neg' if row['pnl_val'] < 0 else ''}'>{row['roi']}</td></tr>" for row in audit_data])}
                    </tbody>
                </table>
            </div>
        </div>
    </body>
    </html>
    """
    
    with tempfile.NamedTemporaryFile('w', delete=False, suffix='.html', encoding='utf-8') as f:
        f.write(html_template)
        temp_path = f.name
        
    webbrowser.open(f"file://{os.path.abspath(temp_path)}")
    print(f"Interactive Audit Dashboard launched in your browser.")

def get_todays_csv():
    today = datetime.now().date()
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    search_dir = os.path.join(project_root, "data", "dropzone")
    csv_files = glob.glob(os.path.join(search_dir, "*.csv"))
    for filepath in csv_files:
        if "tradezella" in filepath.lower():
            continue
        try:
            file_date = datetime.fromtimestamp(os.path.getctime(filepath)).date()
            if file_date == today:
                return filepath
        except OSError:
            continue
    return None

# End of service definition
