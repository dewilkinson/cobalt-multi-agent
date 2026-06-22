import os
import sys
import tkinter as tk
from tkinter import ttk, messagebox
from datetime import datetime, timezone, timedelta
from dotenv import load_dotenv

# Ensure yfinance is installed
try:
    import yfinance as yf
except ImportError:
    print("Please install yfinance: pip install yfinance")
    sys.exit(1)

# Ensure snaptrade is installed
try:
    from snaptrade_client import SnapTrade
except ImportError:
    print("Please install snaptrade_client: pip install snaptrade-client")
    sys.exit(1)

class SnapTradeGUI:
    def __init__(self, root):
        self.root = root
        self.root.title("Portfolio - Loading...")
        self.root.geometry("800x500")
        self.root.configure(bg="#1e1e1e")
        
        self.client = None
        self.user_id = None
        self.user_secret = None
        
        self._setup_ui()
        self._load_credentials()

    def _setup_ui(self):
        style = ttk.Style()
        style.theme_use('clam')
        style.configure("TFrame", background="#1e1e1e")
        style.configure("TLabel", background="#1e1e1e", foreground="#ffffff", font=("Segoe UI", 10))
        style.configure("TButton", font=("Segoe UI", 10, "bold"), background="#007acc", foreground="white")
        style.configure("Treeview", background="#2d2d2d", foreground="white", fieldbackground="#2d2d2d", rowheight=25)
        style.configure("Treeview.Heading", background="#3d3d3d", foreground="white", font=("Segoe UI", 10, "bold"))
        style.map("Treeview", background=[('selected', '#005f9e')])
        
        style.configure("TNotebook", background="#1e1e1e", borderwidth=0)
        style.configure("TNotebook.Tab", background="#2d2d2d", foreground="white", padding=[10, 2])
        style.map("TNotebook.Tab", background=[('selected', '#007acc')], foreground=[('selected', 'white')])
        
        style.configure("TEntry", fieldbackground="#2d2d2d", foreground="white")
        style.map("TEntry", fieldbackground=[('!disabled', '#2d2d2d')], background=[('!disabled', '#2d2d2d')])
        style.configure("TCombobox", fieldbackground="#2d2d2d", background="#2d2d2d", foreground="white")
        style.map("TCombobox", fieldbackground=[('readonly', '#2d2d2d')], selectbackground=[('readonly', '#005f9e')])
        
        # Style the dropdown listbox of the Combobox
        self.root.option_add('*TCombobox*Listbox.background', '#2d2d2d')
        self.root.option_add('*TCombobox*Listbox.foreground', 'white')
        self.root.option_add('*TCombobox*Listbox.selectBackground', '#005f9e')
        self.root.option_add('*TCombobox*Listbox.selectForeground', 'white')
        
        main_frame = ttk.Frame(self.root, padding="15")
        main_frame.pack(fill=tk.BOTH, expand=True)
        
        top_frame = ttk.Frame(main_frame)
        top_frame.pack(fill=tk.X, pady=(0, 5))
        
        self.status_label = ttk.Label(top_frame, text="Status: Loading credentials...")
        self.status_label.pack(side=tk.LEFT)
        
        self.controls_visible = True
        self.toggle_btn = ttk.Button(top_frame, text="Hide Controls", command=self.toggle_controls)
        self.toggle_btn.pack(side=tk.RIGHT)
        
        self.header_frame = ttk.Frame(main_frame)
        self.header_frame.pack(fill=tk.X, pady=(0, 15))
        
        refresh_btn = ttk.Button(self.header_frame, text="Refresh Orders", command=self.fetch_orders)
        refresh_btn.pack(side=tk.RIGHT, padx=5)
        
        self.force_var = tk.BooleanVar(value=False)
        force_check = ttk.Checkbutton(self.header_frame, text="Force Resync", variable=self.force_var)
        force_check.pack(side=tk.RIGHT, padx=5)
        
        self.sym_var = tk.StringVar()
        sym_entry = ttk.Entry(self.header_frame, textvariable=self.sym_var, width=10)
        sym_entry.pack(side=tk.RIGHT, padx=5)
        
        sym_label = ttk.Label(self.header_frame, text="Symbol:")
        sym_label.pack(side=tk.RIGHT)
        
        self.range_var = tk.StringVar(value="Today")
        self.range_combo = ttk.Combobox(self.header_frame, textvariable=self.range_var, values=["Today", "Week", "Month", "90 days", "YTD", "1y"], state="readonly", width=10)
        self.range_combo.pack(side=tk.RIGHT, padx=5)
        
        range_label = ttk.Label(self.header_frame, text="Range:")
        range_label.pack(side=tk.RIGHT)
        
        self.notebook = ttk.Notebook(main_frame)
        self.notebook.pack(fill=tk.BOTH, expand=True)
        
        # Tab 1: Positions
        self.tab_positions = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_positions, text="Positions")
        
        pos_columns = (
            "Symbol", "Last_price", "Today_GL_dlr", "Last_price_change", 
            "Today_GL_pct", "Total_GL_dlr", "Total_GL_pct", "Current_value", 
            "Pct_of_account", "Quantity", "Average_cost", "Cost_basis_total", "Range_52w"
        )
        self.positions_tree = ttk.Treeview(self.tab_positions, columns=pos_columns, show="headings")
        
        self.positions_tree.heading("Symbol", text="Symbol")
        self.positions_tree.heading("Last_price", text="Last price")
        self.positions_tree.heading("Today_GL_dlr", text="Today's gain/loss $")
        self.positions_tree.heading("Last_price_change", text="Last price change")
        self.positions_tree.heading("Today_GL_pct", text="Today's gain/loss %")
        self.positions_tree.heading("Total_GL_dlr", text="Total gain/loss $")
        self.positions_tree.heading("Total_GL_pct", text="Total gain/loss %")
        self.positions_tree.heading("Current_value", text="Current value")
        self.positions_tree.heading("Pct_of_account", text="% of account")
        self.positions_tree.heading("Quantity", text="Quantity")
        self.positions_tree.heading("Average_cost", text="Average cost basis")
        self.positions_tree.heading("Cost_basis_total", text="Cost basis total")
        self.positions_tree.heading("Range_52w", text="52-week range")
        
        for col in pos_columns:
            self.positions_tree.column(col, width=90)
            
        pos_scroll = ttk.Scrollbar(self.tab_positions, orient=tk.VERTICAL, command=self.positions_tree.yview)
        self.positions_tree.configure(yscroll=pos_scroll.set)
        self.positions_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        pos_scroll.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Tab 2: Order History
        self.tab_orders = ttk.Frame(self.notebook)
        self.notebook.add(self.tab_orders, text="Order History")
        
        columns = ("Time", "Account", "Symbol", "Action", "Quantity", "Price", "Status")
        self.tree = ttk.Treeview(self.tab_orders, columns=columns, show="headings")
        
        # Configure columns
        self.tree.heading("Time", text="Time (UTC)")
        self.tree.heading("Account", text="Account")
        self.tree.heading("Symbol", text="Symbol")
        self.tree.heading("Action", text="Action")
        self.tree.heading("Quantity", text="Quantity")
        self.tree.heading("Price", text="Price")
        self.tree.heading("Status", text="Status")
        
        self.tree.column("Time", width=140)
        self.tree.column("Account", width=120)
        self.tree.column("Symbol", width=80)
        self.tree.column("Action", width=80)
        self.tree.column("Quantity", width=80)
        self.tree.column("Price", width=80)
        self.tree.column("Status", width=100)
        
        scrollbar = ttk.Scrollbar(self.tab_orders, orient=tk.VERTICAL, command=self.tree.yview)
        self.tree.configure(yscroll=scrollbar.set)
        
        self.tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)

    def toggle_controls(self):
        if self.controls_visible:
            self.header_frame.pack_forget()
            self.toggle_btn.config(text="Show Controls")
            self.controls_visible = False
        else:
            self.header_frame.pack(fill=tk.X, pady=(0, 15), before=self.notebook)
            self.toggle_btn.config(text="Hide Controls")
            self.controls_visible = True
    def _load_credentials(self):
        base_dir = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
        env_path = os.path.join(base_dir, "backend", ".env")
        if os.path.exists(env_path):
            load_dotenv(env_path, override=True)
                
        client_id = os.getenv("SNAPTRADE_CLIENT_ID")
        consumer_key = os.getenv("SNAPTRADE_CONSUMER_KEY")
        self.user_id = os.getenv("SNAPTRADE_USER_ID")
        self.user_secret = os.getenv("SNAPTRADE_USER_SECRET")
        
        if not all([client_id, consumer_key, self.user_id, self.user_secret]):
            messagebox.showerror("Configuration Error", "Missing SnapTrade credentials in .env file.")
            self.status_label.config(text="Status: Missing Credentials")
            return
            
        try:
            self.client = SnapTrade(client_id=client_id, consumer_key=consumer_key)
            self.status_label.config(text="Status: Ready. Click 'Refresh Orders'.")
            # Auto-fetch on load
            self.root.after(500, self.fetch_orders)
        except Exception as e:
            messagebox.showerror("Init Error", str(e))

    def fetch_orders(self):
        if not self.client:
            return
            
        self.status_label.config(text="Status: Fetching accounts...")
        self.root.update()
        
        # Ensure we can import BrokerageCache
        import sys
        import os
        backend_dir = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "backend"))
        if backend_dir not in sys.path:
            sys.path.append(backend_dir)
        try:
            from src.services.brokerage_cache import BrokerageCache
        except ImportError:
            BrokerageCache = None
            
        try:
            # 1. Fetch Accounts
            accounts_res = self.client.account_information.list_user_accounts(
                user_id=self.user_id, 
                user_secret=self.user_secret
            )
            accounts = getattr(accounts_res, 'body', accounts_res)
            
            # Clear existing items
            for item in self.tree.get_children():
                self.tree.delete(item)
                
            today_dt = datetime.now(timezone.utc)
            today_str = today_dt.strftime("%Y-%m-%d")
            
            selected_range = self.range_var.get()
            if selected_range == "Today":
                target_start_str = today_str
            elif selected_range == "Week":
                target_start_str = (today_dt - timedelta(days=7)).strftime("%Y-%m-%d")
            elif selected_range == "Month":
                target_start_str = (today_dt - timedelta(days=30)).strftime("%Y-%m-%d")
            elif selected_range == "90 days":
                target_start_str = (today_dt - timedelta(days=90)).strftime("%Y-%m-%d")
            elif selected_range == "YTD":
                target_start_str = datetime(today_dt.year, 1, 1, tzinfo=timezone.utc).strftime("%Y-%m-%d")
            elif selected_range == "1y":
                target_start_str = (today_dt - timedelta(days=365)).strftime("%Y-%m-%d")
            else:
                target_start_str = today_str
                
            # Determine API fetch bounds
            if self.force_var.get():
                fetch_start_str = target_start_str
            else:
                fetch_start_str = (today_dt - timedelta(days=3)).strftime("%Y-%m-%d")
                
            total_orders_found = 0
            
            # 2. Fetch Orders for each account
            for acc in accounts:
                acc_name = acc.get('name', 'Unknown')
                acc_id = acc.get('id')
                acc_num = acc.get('number', str(acc_id))
                masked_num = "x" * (len(acc_num) - 4) + acc_num[-4:] if len(acc_num) > 4 else acc_num
                self.root.title(f"Portfolio - {acc_name}, {masked_num}")
                if not acc_id:
                    continue
                    
                self.status_label.config(text=f"Status: Fetching orders for {acc_name}...")
                self.root.update()
                
                try:
                    # We request recent activities to get executed trades for today
                    activities_res = self.client.transactions_and_reporting.get_activities(
                        user_id=self.user_id,
                        user_secret=self.user_secret,
                        accounts=acc_id,
                        start_date=fetch_start_str,
                        end_date=today_str
                    )
                    fetched_activities = getattr(activities_res, 'body', activities_res)
                    if not isinstance(fetched_activities, list):
                        fetched_activities = []
                except Exception as e:
                    print(f"Error fetching: {e}")
                    fetched_activities = []
                    
                if BrokerageCache:
                    activities = BrokerageCache.merge_activities(acc_id, fetched_activities)
                else:
                    activities = fetched_activities
                    
                # Filter cached activities to the requested range
                filtered_activities = []
                for act in activities:
                    placed_time = act.get('trade_date', act.get('time_placed', ''))
                    if placed_time:
                        date_only = placed_time[:10]
                        if target_start_str <= date_only <= today_str:
                            filtered_activities.append(act)
                fetched_activities = filtered_activities
                
                # Fetch live orders to catch today's executed trades before midnight settlement
                try:
                    orders_res = self.client.account_information.get_user_account_orders(
                        user_id=self.user_id,
                        user_secret=self.user_secret,
                        account_id=acc_id,
                        state="all"
                    )
                    orders = getattr(orders_res, 'body', orders_res)
                    if isinstance(orders, list):
                        for o in orders:
                            # Normalize Order schema to match Activity schema
                            if 'id' not in o and 'brokerage_order_id' in o:
                                o['id'] = str(o['brokerage_order_id'])
                            if 'type' not in o and 'action' in o:
                                o['type'] = str(o['action'])
                            if 'units' not in o and 'filled_quantity' in o:
                                o['units'] = float(o.get('filled_quantity', 0) or 0)
                            if 'price' not in o and 'execution_price' in o:
                                o['price'] = float(o.get('execution_price', 0) or 0)
                            if 'trade_date' not in o and 'time_placed' in o:
                                o['trade_date'] = str(o['time_placed'])
                        fetched_activities.extend(orders)
                except Exception as e:
                    print(f"Error fetching open orders: {e}")
                    
                if BrokerageCache:
                    activities = BrokerageCache.merge_activities(acc_id, fetched_activities)
                else:
                    activities = fetched_activities

                # -----------------------------------------------------------------
                # POSITION MANAGER AGGREGATION (Requires ALL historical activities)
                # -----------------------------------------------------------------
                open_positions = {}
                # Sort from oldest to newest to replay trades in chronological order
                historical_activities = sorted(activities, key=lambda x: x.get('trade_date', x.get('time_placed', '')))
                
                for act in historical_activities:
                    action = act.get('action', act.get('type', '')).upper()
                    if action not in ["BUY", "SELL", "BOUGHT", "SOLD"]:
                        continue
                        
                    sym_field = act.get('symbol')
                    if isinstance(sym_field, dict):
                        symbol = sym_field.get('symbol') or sym_field.get('raw_symbol', 'UNKNOWN')
                    elif isinstance(sym_field, str):
                        # It might be a GUID, check universal_symbol
                        univ_sym = act.get('universal_symbol')
                        if isinstance(univ_sym, dict):
                            symbol = univ_sym.get('symbol', sym_field)
                        else:
                            symbol = sym_field
                    else:
                        symbol = 'UNKNOWN'
                        
                    if symbol == 'UNKNOWN':
                        continue
                        
                    qty = float(act.get('units', act.get('total_quantity', act.get('open_quantity', 0))))
                    price = float(act.get('price', act.get('execution_price', 0)) or 0)
                    
                    if symbol not in open_positions:
                        open_positions[symbol] = {'quantity': 0, 'cost_basis_total': 0, 'average_cost': 0}
                        
                    pos = open_positions[symbol]
                    
                    if action in ["BUY", "BOUGHT"]:
                        new_qty = pos['quantity'] + qty
                        new_cost = pos['cost_basis_total'] + (qty * price)
                        pos['quantity'] = new_qty
                        pos['cost_basis_total'] = new_cost
                        pos['average_cost'] = new_cost / new_qty if new_qty > 0 else 0
                    elif action in ["SELL", "SOLD"]:
                        new_qty = pos['quantity'] - qty
                        if new_qty <= 0:
                            pos['quantity'] = 0
                            pos['cost_basis_total'] = 0
                            pos['average_cost'] = 0
                        else:
                            pos['cost_basis_total'] -= (qty * pos['average_cost'])
                            pos['quantity'] = new_qty
                            
                # Filter out closed positions
                active_symbols = {sym: pos for sym, pos in open_positions.items() if pos['quantity'] > 0}
                
                # Fetch live data via yfinance for open positions
                if active_symbols:
                    self.status_label.config(text=f"Status: Fetching live quotes for {len(active_symbols)} positions...")
                    self.root.update()
                    try:
                        tickers_obj = yf.Tickers(" ".join(active_symbols.keys()))
                        
                        # Clear existing items in positions tree
                        for item in self.positions_tree.get_children():
                            self.positions_tree.delete(item)
                            
                        current_prices = {}
                        for sym in active_symbols.keys():
                            try:
                                ticker = tickers_obj.tickers[sym]
                                last_price = ticker.fast_info.get('lastPrice', 0)
                                if not last_price or last_price == 0:
                                    last_price = active_symbols[sym]['average_cost']
                                current_prices[sym] = {
                                    'last_price': last_price,
                                    'prev_close': ticker.fast_info.get('previousClose', last_price),
                                    'year_high': ticker.fast_info.get('yearHigh', 0),
                                    'year_low': ticker.fast_info.get('yearLow', 0)
                                }
                            except Exception:
                                current_prices[sym] = {
                                    'last_price': active_symbols[sym]['average_cost'],
                                    'prev_close': active_symbols[sym]['average_cost'],
                                    'year_high': 0,
                                    'year_low': 0
                                }
                                
                        total_acct_value = sum(active_symbols[sym]['quantity'] * current_prices[sym]['last_price'] for sym in active_symbols.keys())
                        if total_acct_value == 0: total_acct_value = 1
                        
                        for sym, pos in active_symbols.items():
                            qty = pos['quantity']
                            avg_cost = pos['average_cost']
                            cost_total = pos['cost_basis_total']
                            
                            price_data = current_prices[sym]
                            last_price = price_data['last_price']
                            prev_close = price_data['prev_close']
                            
                            current_value = qty * last_price
                            pct_account = (current_value / total_acct_value) * 100
                            
                            last_price_change = last_price - prev_close
                            
                            total_gl_dlr = current_value - cost_total
                            total_gl_pct = (total_gl_dlr / cost_total * 100) if cost_total > 0 else 0
                            
                            today_gl_dlr = qty * last_price_change
                            today_gl_pct = (last_price_change / prev_close * 100) if prev_close > 0 else 0
                            
                            rng_52w = f"${price_data['year_low']:.2f} - ${price_data['year_high']:.2f}"
                            
                            tag = "pos" if total_gl_dlr >= 0 else "neg"
                            self.positions_tree.insert("", tk.END, values=(
                                sym,
                                f"${last_price:.2f}",
                                f"{'+' if today_gl_dlr >= 0 else ''}${today_gl_dlr:.2f}",
                                f"{'+' if last_price_change >= 0 else ''}${last_price_change:.2f}",
                                f"{'+' if today_gl_pct >= 0 else ''}{today_gl_pct:.2f}%",
                                f"{'+' if total_gl_dlr >= 0 else ''}${total_gl_dlr:.2f}",
                                f"{'+' if total_gl_pct >= 0 else ''}{total_gl_pct:.2f}%",
                                f"${current_value:.2f}",
                                f"{pct_account:.2f}%",
                                f"{qty:g}",
                                f"${avg_cost:.2f}",
                                f"${cost_total:.2f}",
                                rng_52w
                            ), tags=(tag,))
                            
                        self.positions_tree.tag_configure("pos", foreground="green")
                        self.positions_tree.tag_configure("neg", foreground="red")
                            
                    except Exception as e:
                        print(f"Error fetching live data: {e}")
                # -----------------------------------------------------------------

                # Filter the full cached activities to match the client's requested date range
                filtered_activities = []
                for act in activities:
                    placed_time = act.get('trade_date', act.get('time_placed', ''))
                    if placed_time:
                        date_only = placed_time[:10]
                        if target_start_str <= date_only <= today_str:
                            filtered_activities.append(act)
                activities = filtered_activities

                # Reverse activities to process oldest first (for correct chronological timestamping)
                activities = list(reversed(activities))
                daily_counters = {}
                
                processed_orders = []
                for order in activities:
                    action = order.get('action', order.get('type', 'N/A')).upper()
                    if action not in ["BUY", "SELL", "BOUGHT", "SOLD"]:
                        continue
                        
                    placed_time = order.get('trade_date', order.get('time_placed', ''))
                    date_only = placed_time[:10] if placed_time else "Unknown"
                    time_part = placed_time[11:] if placed_time and len(placed_time) > 11 else ""
                    
                    # Check if we have a real bridged time vs a default SnapTrade midnight UTC/EDT time
                    is_real_time = False
                    if time_part and not (time_part.startswith('00:00') or time_part.startswith('04:00') or time_part.startswith('05:00')):
                        is_real_time = True
                        
                    if is_real_time:
                        order['_fmt_time'] = f"{date_only} {time_part.replace('Z', '')}"
                    else:
                        if date_only not in daily_counters:
                            daily_counters[date_only] = 0
                        
                        daily_counters[date_only] += 1
                        seconds = daily_counters[date_only]
                        minutes = seconds // 60
                        remaining_secs = seconds % 60
                        synth_time = f"09:{30 + minutes:02d}:{remaining_secs:02d}"
                        
                        order['_fmt_time'] = f"{date_only} {synth_time}" if date_only != "Unknown" else "Unknown"
                    processed_orders.append(order)
                    
                # Reverse back so newest is shown at the top of the GUI
                processed_orders = list(reversed(processed_orders))
                
                for order in processed_orders:
                    sym_field = order.get('symbol')
                    if isinstance(sym_field, dict):
                        symbol = sym_field.get('symbol') or sym_field.get('raw_symbol', 'N/A')
                    elif isinstance(sym_field, str):
                        univ_sym = order.get('universal_symbol')
                        if isinstance(univ_sym, dict):
                            symbol = univ_sym.get('symbol', sym_field)
                        else:
                            symbol = sym_field
                    else:
                        symbol = 'N/A'
                    
                    sym_filter = self.sym_var.get().strip().upper()
                    if sym_filter and sym_filter != symbol.upper():
                        continue
                        
                    action = order.get('action', order.get('type', 'N/A')).upper()
                    qty = order.get('units', order.get('total_quantity', order.get('open_quantity', 0)))
                    price = order.get('price') or order.get('stop_price') or 'MKT'
                    status = order.get('state', 'Executed').capitalize()
                    
                    fmt_time = order.get('_fmt_time', 'Unknown')
                    
                    self.tree.insert("", tk.END, values=(
                        fmt_time,
                        acc_name,
                        symbol,
                        action,
                        qty,
                        f"${price}" if isinstance(price, (int, float)) else price,
                        status
                    ))
                    total_orders_found += 1
                        
            self.status_label.config(text=f"Status: Done. Loaded {total_orders_found} orders for today.")
        except Exception as e:
            messagebox.showerror("API Error", f"Failed to fetch data: {e}")
            self.status_label.config(text="Status: API Error")

if __name__ == "__main__":
    root = tk.Tk()
    app = SnapTradeGUI(root)
    root.mainloop()
