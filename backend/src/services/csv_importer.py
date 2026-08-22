import os
import csv
import io
import datetime
import glob
import logging
import re
from src.config.loader import get_config

logger = logging.getLogger(__name__)

def parse_fidelity_orders(csv_path: str):
    if not os.path.exists(csv_path):
        return {}

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()

    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Symbol,Action,Amount"):
            header_idx = i
            break
            
    if header_idx == -1:
        return {}

    csv_data = "".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_data))
    
    activities_by_account = {}
    
    for row in reader:
        sym = (row.get("Symbol") or "").upper().strip()
        status = row.get("Status") or ""
        order_time_str = row.get("Order Time") or ""
        action = (row.get("Action") or "").upper()
        account = (row.get("Account") or "mock-fidelity-1").strip()
        
        if sym and order_time_str and ("Filled" in status or "Open" in status):
            final_status = "Executed" if "Filled" in status else "Open"
            
            price_str = status.split("$")[-1] if "$" in status and "Filled" in status else "0"
            try:
                price = float(price_str.replace(',', ''))
            except:
                price = 0.0
                
            qty_str = row.get("Amount", "0")
            try:
                qty = float(qty_str.replace(',', ''))
            except:
                qty = 0.0

            clean_time = order_time_str.split(" ET ")[0] if " ET " in order_time_str else order_time_str
            date_str = order_time_str.split(" ET ")[-1] if " ET " in order_time_str else ""
            try:
                dt_obj = datetime.datetime.strptime(f"{clean_time} {date_str}", "%I:%M:%S %p %b-%d-%Y")
                iso_time = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception as e:
                iso_time = order_time_str
                
            activity_id = f"ATP-{sym}-{iso_time}-{qty}-{action}".replace(":", "").replace(" ", "-")
            
            activity = {
                "id": activity_id,
                "type": action,
                "units": qty,
                "price": price,
                "trade_date": iso_time,
                "status": final_status,
                "symbol": {
                    "symbol": sym
                }
            }
            if account not in activities_by_account:
                activities_by_account[account] = []
            activities_by_account[account].append(activity)
            
    return activities_by_account

def parse_fidelity_history(csv_path: str):
    if not os.path.exists(csv_path): return {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    
    header_idx = -1
    is_activity = False
    for i, line in enumerate(lines):
        if line.startswith("Run Date,Account"):
            header_idx = i
            break
        elif line.startswith("Description,Symbol,Quantity"):
            header_idx = i
            is_activity = True
            break
            
    if header_idx == -1: return {}
    
    csv_data = "".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_data))
    
    activities_by_account = {}
    
    for row in reader:
        if is_activity:
            action_desc = (row.get("Description") or "").upper()
            sym = (row.get("Symbol") or "").upper().strip()
            account = (row.get("Account") or "mock-fidelity-1").strip()
            qty_str = (row.get("Quantity") or "0").replace(',', '')
            price_str = (row.get("Price") or "0").replace(',', '').replace('$', '')
            date_str = row.get("Settlement Date") or ""
        else:
            action_desc = (row.get("Action") or "").upper()
            sym = (row.get("Symbol") or "").upper().strip()
            account_name = (row.get("Account") or "").strip()
            account_num = (row.get("Account Number") or "").strip()
            account = f"{account_name} *{account_num[-4:]}" if account_name and account_num else "mock-fidelity-1"
            
            qty_str = (row.get("Quantity") or "0").replace(',', '')
            price_str = (row.get("Price ($)") or "0").replace(',', '')
            date_str = row.get("Run Date") or ""
        
        action = ""
        if "BOUGHT" in action_desc: action = "BUY"
        elif "SOLD" in action_desc: action = "SELL"
        elif "REINVEST" in action_desc: action = "REINVEST"
        elif "DIVIDEND" in action_desc: action = "DIVIDEND"
        
        if not action or not sym: continue
            
        try:
            qty = abs(float(qty_str)) # history has negative qty for sells
            price = float(price_str)
        except:
            continue
            
        try:
            dt_obj = datetime.datetime.strptime(date_str, "%m/%d/%Y")
            iso_time = dt_obj.strftime("%Y-%m-%dT00:00:00.000Z")
        except:
            iso_time = date_str
            
        activity_id = f"HIST-{sym}-{iso_time}-{qty}-{action}".replace(":", "").replace(" ", "-")
        activity = {
            "id": activity_id,
            "type": action,
            "units": qty,
            "price": price,
            "trade_date": iso_time,
            "status": "Executed",
            "symbol": {"symbol": sym}
        }
        
        if account not in activities_by_account:
            activities_by_account[account] = []
        activities_by_account[account].append(activity)
        
    return activities_by_account

def parse_fidelity_positions(csv_path: str):
    if not os.path.exists(csv_path): return {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    
    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Symbol,Quantity,Last"):
            header_idx = i
            break
            
    if header_idx == -1: return {}
    
    csv_data = "".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_data))
    
    positions_by_account = {}
    for row in reader:
        sym = (row.get("Symbol") or "").strip()
        qty_str = (row.get("Quantity") or "0").replace('"', '').replace(',', '')
        cost_str = (row.get("$ Avg Cost") or "0").replace('"', '').replace(',', '')
        day_gl_str = (row.get("$ Day G/L") or "0").replace('"', '').replace(',', '')
        total_gl_str = (row.get("$ Total G/L") or "0").replace('"', '').replace(',', '')
        
        raw_account = row.get("Account")
        if not raw_account:
            logger.warning(f"Account field missing for position {sym}, falling back to __POSITIONS__")
        
        account = (raw_account or "__POSITIONS__").strip()
        
        try:
            qty = float(qty_str)
        except:
            qty = 0.0
        try:
            cost = float(cost_str)
        except:
            cost = 0.0
        try:
            day_gl = float(day_gl_str)
        except:
            day_gl = 0.0
        try:
            total_gl = float(total_gl_str)
        except:
            total_gl = 0.0
            
        if sym and qty > 0:
            if account not in positions_by_account:
                positions_by_account[account] = []
            positions_by_account[account].append({
                "symbol": sym,
                "quantity": qty,
                "average_cost": cost,
                "todays_gl_dol": day_gl,
                "total_gl_dol": total_gl,
                "total_cost": qty * cost
            })
            
    return positions_by_account

def parse_fidelity_closed_positions(csv_path: str):
    if not os.path.exists(csv_path): return {}
    with open(csv_path, "r", encoding="utf-8-sig") as f:
        lines = f.readlines()
    
    # Extract 'as of' date from header (e.g. 'as of 05/06/2026 at 08:00:12 AM')
    as_of_date_str = "Unknown"
    for line in lines[:5]:
        if "as of" in line:
            parts = line.split("as of ")
            if len(parts) > 1:
                as_of_date_str = parts[1].split(" at ")[0].strip()
                break

    # Reformat date to standard YYYY-MM-DD
    target_date = datetime.datetime.now().strftime("%Y-%m-%d")
    if as_of_date_str != "Unknown":
        try:
            target_date = datetime.datetime.strptime(as_of_date_str, "%m/%d/%Y").strftime("%Y-%m-%d")
        except:
            pass

    header_idx = -1
    for i, line in enumerate(lines):
        if line.startswith("Symbol,Quantity,Last,Avg Proceeds"):
            header_idx = i
            break
            
    if header_idx == -1: return {}
    
    csv_data = "".join(lines[header_idx:])
    reader = csv.DictReader(io.StringIO(csv_data))
    
    closed_positions_by_account = {}
    row_count = 0
    
    for row in reader:
        sym = (row.get("Symbol") or "").strip()
        if sym == "Totals" or not sym:
            continue
            
        qty_str = (row.get("Quantity") or "0").replace('"', '').replace(',', '')
        avg_proceeds_str = (row.get("Avg Proceeds") or "0").replace('"', '').replace(',', '')
        avg_cost_str = (row.get("Avg Cost") or "0").replace('"', '').replace(',', '')
        total_gl_str = (row.get("$ Total G/L") or "0").replace('"', '').replace(',', '')
        
        raw_account = row.get("Account")
        account = (raw_account or "__POSITIONS__").strip()
        
        try:
            qty = float(qty_str)
            sell_price = float(avg_proceeds_str)
            buy_price = float(avg_cost_str)
            pnl = float(total_gl_str)
        except:
            continue
            
        if qty > 0:
            if account not in closed_positions_by_account:
                closed_positions_by_account[account] = []
                
            # Chronological algorithm logic
            seconds = row_count + 1
            minutes = seconds // 60
            remaining_secs = seconds % 60
            buy_time_str = f"{target_date} 09:{30 + minutes:02d}:{remaining_secs:02d}"
            
            # Add 1 second for the sell to ensure it occurs after the buy
            sell_seconds = seconds + 1
            sell_minutes = sell_seconds // 60
            sell_rem_secs = sell_seconds % 60
            sell_time_str = f"{target_date} 09:{30 + sell_minutes:02d}:{sell_rem_secs:02d}"
            
            closed_positions_by_account[account].append({
                "symbol": sym,
                "qty": qty,
                "buy_price": buy_price,
                "sell_price": sell_price,
                "buy_time": buy_time_str,
                "close_date": sell_time_str,
                "pnl": pnl,
                "pnl_pct": ((sell_price - buy_price) / buy_price * 100) if buy_price > 0 else 0.0
            })
            row_count += 2
            
    return closed_positions_by_account


def parse_tradingview_paper_trading(csv_path: str):
    if not os.path.exists(csv_path):
        return {}
        
    stock_activities = []
    futures_activities = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            if "Status" in row:
                if row.get("Status") != "Filled":
                    continue
            else:
                if not row.get("Fill price"):
                    continue
                
            symbol_raw = row.get("Symbol") or ""
            
            # Determine if this is a futures contract (contains exchange prefix for futures, or ends with '!')
            is_futures = False
            exchange = ""
            if ":" in symbol_raw:
                parts = symbol_raw.split(":")
                exchange = parts[0].upper().strip()
                symbol_name = parts[-1].upper().strip()
            else:
                symbol_name = symbol_raw.upper().strip()
                
            if exchange in ["CME", "COMEX", "COMEX_MINI", "NYMEX", "CBOT", "ICE"] or symbol_name.endswith("!"):
                is_futures = True
                
            # Clean symbol name
            # Strip any continuous contract suffix like '1!', '2!'
            if symbol_name.endswith("!"):
                symbol_name = symbol_name.rstrip("!")
                # strip trailing digits
                while symbol_name and symbol_name[-1].isdigit():
                    symbol_name = symbol_name[:-1]
                    
            if is_futures:
                sym = f"/{symbol_name}"
            else:
                sym = symbol_name
            
            side = (row.get("Side") or "").upper().strip() # BUY or SELL
            action = "Buy" if side == "BUY" else "Sell"
            
            qty_str = row.get("Quantity", "0")
            try:
                qty = float(qty_str.replace(',', ''))
            except:
                qty = 0.0
                
            price_str = row.get("Fill price", "0")
            try:
                price = float(price_str.replace(',', ''))
            except:
                price = 0.0
                
            closing_time = row.get("Closing time") or "" # "2026-06-25 15:28:58"
            
            # Format closing time to ISO string (TradingView CSV timestamps are in UTC)
            try:
                from zoneinfo import ZoneInfo
                utc = ZoneInfo("UTC")
                dt_obj = datetime.datetime.strptime(closing_time, "%Y-%m-%d %H:%M:%S").replace(tzinfo=utc)
                iso_time = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception:
                iso_time = closing_time
                
            order_id = row.get("Order ID") or ""
            activity_id = f"TV-{sym}-{iso_time}-{qty}-{action}-{order_id}".replace(":", "").replace(" ", "-")
            
            activity = {
                "id": activity_id,
                "type": action,
                "units": qty,
                "price": price,
                "trade_date": iso_time,
                "status": "Executed",
                "symbol": {
                    "symbol": sym
                }
            }
            if is_futures:
                futures_activities.append(activity)
            else:
                stock_activities.append(activity)
                
    res = {}
    if stock_activities:
        res["TradingView Paper Stocks"] = stock_activities
    if futures_activities:
        res["TradingView Paper Futures"] = futures_activities
    return res


def parse_tradingview_replay_report(csv_path: str):
    if not os.path.exists(csv_path):
        return {}

    filename = os.path.basename(csv_path)
    sym = "/MES"
    sym_match = re.search(r'([A-Z0-9]{2,6}!?)', filename.upper())
    if sym_match:
        raw_sym = sym_match.group(1).rstrip("!")
        while raw_sym and raw_sym[-1].isdigit():
            raw_sym = raw_sym[:-1]
        if raw_sym:
            sym = f"/{raw_sym}" if not raw_sym.startswith("/") else raw_sym

    activities = []
    trades_by_num = {}

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        reader = list(csv.DictReader(f))

    for row in reader:
        trade_num = (row.get("Trade number") or row.get("Trade #") or "").strip()
        t_type = (row.get("Type") or "").strip().lower()
        dt_str = (row.get("Date and time") or row.get("Date/Time") or row.get("Time") or "").strip()
        price_str = (row.get("Price USD") or row.get("Price") or "0").replace(',', '')
        qty_str = (row.get("Size (qty)") or row.get("Quantity") or row.get("Size") or "0").replace(',', '')
        pnl_str = (row.get("Net PnL USD") or row.get("Net PnL") or row.get("PnL") or "0").replace(',', '')
        comm_str = (row.get("Commission USD") or row.get("Commission") or "0").replace(',', '')

        try:
            price = float(price_str)
            qty = float(qty_str)
            pnl = float(pnl_str)
            comm = float(comm_str)
        except Exception:
            continue

        if qty <= 0:
            continue

        iso_time = dt_str
        try:
            if " " in dt_str:
                dt_obj = datetime.datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
            else:
                dt_obj = datetime.datetime.strptime(dt_str, "%Y-%m-%d")
            iso_time = dt_obj.strftime("%Y-%m-%dT%H:%M:%S.000Z")
        except Exception:
            pass

        is_entry = "entry" in t_type
        is_short = "short" in t_type

        if (is_entry and not is_short) or (not is_entry and is_short):
            action = "BUY"
        else:
            action = "SELL"

        act_id = f"REPLAY-{sym}-{iso_time}-{trade_num}-{action}".replace(":", "").replace(" ", "-")
        activities.append({
            "id": act_id,
            "type": action,
            "units": qty,
            "price": price,
            "trade_date": iso_time,
            "fee": comm,
            "status": "Executed",
            "symbol": {"symbol": sym}
        })

        if trade_num:
            if trade_num not in trades_by_num:
                trades_by_num[trade_num] = {}
            if is_entry:
                trades_by_num[trade_num]["entry"] = {"price": price, "date": iso_time, "qty": qty, "is_short": is_short}
            else:
                trades_by_num[trade_num]["exit"] = {"price": price, "date": iso_time, "pnl": pnl, "comm": comm}

    closed_positions = []
    for t_num, t_data in trades_by_num.items():
        entry = t_data.get("entry")
        exit_data = t_data.get("exit")
        if entry and exit_data:
            is_short = entry.get("is_short", False)
            buy_price = exit_data["price"] if is_short else entry["price"]
            sell_price = entry["price"] if is_short else exit_data["price"]
            closed_positions.append({
                "symbol": sym,
                "open_date": entry["date"],
                "close_date": exit_data["date"],
                "qty": entry["qty"],
                "buy_price": buy_price,
                "sell_price": sell_price,
                "pnl": round(exit_data["pnl"], 2),
                "fees": round(exit_data.get("comm", 0), 2),
                "direction": "Short" if is_short else "Long"
            })

    target_acct = "Replay Trades"
    return {
        "activities": {target_acct: activities},
        "closed_positions": {target_acct: closed_positions}
    }


def parse_topstepx_trades(csv_path: str):
    if not os.path.exists(csv_path):
        return {}

    with open(csv_path, "r", encoding="utf-8-sig", errors="ignore") as f:
        file_text = f.read()

    fname = os.path.basename(csv_path).lower()
    full_path_str = os.path.abspath(csv_path).lower()
    full_search_text = f"{full_path_str} {file_text.lower()}"

    # Determine default target TopStep account by checking for account identifiers in path, filename, or file text
    default_account = None
    if any(k in full_search_text for k in ["7328", "5972", "7952", "7925", "50287952"]):
        default_account = "TopStepX Express *7328"
    elif any(k in full_search_text for k in ["7085", "4889", "81134889"]):
        default_account = "TopStepX Combine *7085"
    elif "1299" in full_search_text:
        default_account = "TopStepX Combine *1299"
    elif "5496" in full_search_text:
        default_account = "TopStepX Combine *5496"
    elif "2210" in full_search_text:
        default_account = "TopStepX Express *2210"
    elif any(k in full_search_text for k in ["topstep", "trades_export"]):
        default_account = "TopStepX Express *2210"

    activities_by_account = {}
    closed_positions_by_account = {}

    with open(csv_path, "r", encoding="utf-8-sig") as f:
        reader = list(csv.DictReader(f))

    for row in reader:
        # Check per-row account if present
        row_acct_raw = str(row.get("Account") or row.get("Account Name") or row.get("Account Number") or "").lower()
        target_account = None
        if any(k in row_acct_raw for k in ["7328", "5972", "7952", "7925", "50287952"]):
            target_account = "TopStepX Express *7328"
        elif any(k in row_acct_raw for k in ["7085", "4889", "81134889"]):
            target_account = "TopStepX Combine *7085"
        elif "1299" in row_acct_raw:
            target_account = "TopStepX Combine *1299"
        elif "5496" in row_acct_raw:
            target_account = "TopStepX Combine *5496"
        elif "2210" in row_acct_raw:
            target_account = "TopStepX Express *2210"
        else:
            target_account = default_account

        # Mandatory rule: Do not process topstep csv files that do not contain valid account target
        if not target_account:
            continue

        trade_id = (row.get("Id") or "").strip()
        raw_sym = (row.get("ContractName") or "").strip().upper()
        if not raw_sym:
            continue

        clean_sym = re.sub(r'[FGHJKMNQUVXZ]\d{1,2}$', '', raw_sym)
        if not clean_sym:
            clean_sym = raw_sym
        if not clean_sym.startswith("/"):
            sym = f"/{clean_sym}"
        else:
            sym = clean_sym

        trade_type = (row.get("Type") or "").strip().lower()
        qty_str = (row.get("Size") or "0").replace(',', '')
        try:
            qty = float(qty_str)
        except Exception:
            qty = 0.0

        if qty <= 0:
            continue

        entry_price_str = (row.get("EntryPrice") or "0").replace(',', '')
        exit_price_str = (row.get("ExitPrice") or "0").replace(',', '')
        try:
            entry_price = float(entry_price_str)
            exit_price = float(exit_price_str)
        except Exception:
            continue

        entered_at = (row.get("EnteredAt") or "").strip()
        exited_at = (row.get("ExitedAt") or "").strip()

        def parse_topstep_time(t_str):
            if not t_str:
                return ""
            try:
                parts = t_str.split(" ")
                dt_part = f"{parts[0]} {parts[1]}"
                dt_obj = datetime.datetime.strptime(dt_part, "%m/%d/%Y %H:%M:%S")
                
                from zoneinfo import ZoneInfo
                eastern = ZoneInfo("America/New_York")
                utc = ZoneInfo("UTC")
                dt_est = dt_obj.replace(tzinfo=eastern)
                dt_utc = dt_est.astimezone(utc)
                return dt_utc.strftime("%Y-%m-%dT%H:%M:%S.000Z")
            except Exception:
                return t_str

        entry_iso = parse_topstep_time(entered_at)
        exit_iso = parse_topstep_time(exited_at)

        if trade_type == "short":
            entry_action = "SELL"
            exit_action = "BUY"
        else:
            entry_action = "BUY"
            exit_action = "SELL"

        fees_str = (row.get("Fees") or "0").replace(',', '')
        comm_str = (row.get("Commissions") or "0").replace(',', '')
        try:
            trade_fee = float(fees_str) + float(comm_str)
        except Exception:
            trade_fee = 0.0
        fill_fee = round(trade_fee / 2.0, 4)

        entry_act_id = f"TOPSTEP-ENTRY-{sym}-{entry_iso}-{qty}-{entry_action}-{trade_id}".replace(":", "").replace(" ", "-")
        exit_act_id = f"TOPSTEP-EXIT-{sym}-{exit_iso}-{qty}-{exit_action}-{trade_id}".replace(":", "").replace(" ", "-")

        if target_account not in activities_by_account:
            activities_by_account[target_account] = []
            closed_positions_by_account[target_account] = []

        activities_by_account[target_account].append({
            "id": entry_act_id,
            "type": entry_action,
            "units": qty,
            "price": entry_price,
            "trade_date": entry_iso,
            "fee": fill_fee,
            "status": "Executed",
            "symbol": {"symbol": sym}
        })

        activities_by_account[target_account].append({
            "id": exit_act_id,
            "type": exit_action,
            "units": qty,
            "price": exit_price,
            "trade_date": exit_iso,
            "fee": fill_fee,
            "status": "Executed",
            "symbol": {"symbol": sym}
        })

        pnl_val = float(row.get("PnL") or "0")
        closed_positions_by_account[target_account].append({
            "symbol": sym,
            "close_date": exit_iso,
            "open_date": entry_iso,
            "qty": qty,
            "buy_price": entry_price if trade_type != "short" else exit_price,
            "sell_price": exit_price if trade_type != "short" else entry_price,
            "pnl": round(pnl_val, 2),
            "fees": round(trade_fee, 2),
            "direction": "Short" if trade_type == "short" else "Long"
        })

    if not activities_by_account:
        logger.info(
            f"TopStep CSV {csv_path}: File contains 0 trade executions or header-only content."
        )
        return {}

    return {"activities": activities_by_account, "closed_positions": closed_positions_by_account}


def get_dropzone_csvs(optional_path=None):
    """Legacy helper for backwards compatibility."""
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    search_dir = optional_path if optional_path else os.path.join(project_root, "data", "dropzone")
    csvs = {"orders": None, "history": None, "positions": None, "closed_positions": None, "paper_trading": None}
    
    if os.path.isfile(search_dir) and search_dir.endswith('.csv'):
        all_csvs = [search_dir]
    else:
        all_csvs = glob.glob(os.path.join(search_dir, "*.csv"))
        all_csvs.sort(key=os.path.getctime, reverse=True)
    
    for c in all_csvs:
        lower_name = os.path.basename(c).lower()
        if "paper-trading-order-history" in lower_name and not csvs["paper_trading"]:
            csvs["paper_trading"] = c
        elif "orders" in lower_name and not csvs["orders"]:
            csvs["orders"] = c
        elif ("history" in lower_name or "activity" in lower_name) and not csvs["history"]:
            csvs["history"] = c
        elif "positions" in lower_name and "closed" not in lower_name and not csvs["positions"]:
            csvs["positions"] = c
        elif "closed_positions" in lower_name and not csvs["closed_positions"]:
            csvs["closed_positions"] = c
            
    return csvs

def get_tradingview_csv_asset_type(csv_path: str) -> str:
    """
    Examines all tickers in the TradingView paper trading CSV.
    Returns 'STOCKS' if all filled symbols are stocks/index funds.
    Returns 'FUTURES' if any filled symbols are futures.
    """
    if not os.path.exists(csv_path):
        return ""
        
    has_stocks = False
    has_futures = False
    
    try:
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.DictReader(f)
            if not reader or not reader.fieldnames:
                return ""
            for row in reader:
                if "Status" in row:
                    if row.get("Status") != "Filled":
                        continue
                else:
                    if not row.get("Fill price"):
                        continue
                symbol_raw = row.get("Symbol") or ""
                if not symbol_raw:
                    continue
                    
                is_futures = False
                exchange = ""
                if ":" in symbol_raw:
                    parts = symbol_raw.split(":")
                    exchange = parts[0].upper().strip()
                    symbol_name = parts[-1].upper().strip()
                else:
                    symbol_name = symbol_raw.upper().strip()
                    
                if exchange in ["CME", "COMEX", "COMEX_MINI", "NYMEX", "CBOT", "ICE"] or symbol_name.endswith("!"):
                    is_futures = True
                    
                if is_futures:
                    has_futures = True
                else:
                    has_stocks = True
    except Exception as e:
        logger.error(f"Error checking asset type for TradingView CSV {csv_path}: {e}")
        return ""
        
    if has_futures:
        return "FUTURES"
    elif has_stocks:
        return "STOCKS"
    return ""

def check_and_backup_dropzone_file(csv_path: str, prefix: str = ""):
    if not csv_path or not os.path.exists(csv_path):
        return
        
    contains_date_time = False
    try:
        with open(csv_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            first_lines = "".join([f.readline() for _ in range(50)])
            if "Order Time" in first_lines or ("Date" in first_lines and "Time" in first_lines) or "Closing time" in first_lines or "EnteredAt" in first_lines or "ExitedAt" in first_lines:
                contains_date_time = True
    except Exception as e:
        logger.error(f"Error checking headers of {csv_path}: {e}")
        
    if contains_date_time:
        import shutil
        from src.services.brokerage_cache import BrokerageCache
        
        try:
            backup_dir = BrokerageCache.get_backup_dir()
            os.makedirs(backup_dir, exist_ok=True)
            
            base, ext = os.path.splitext(os.path.basename(csv_path))
            timestamp = datetime.datetime.now().strftime("%Y-%m-%d_%H%M%S")
            backup_filename = f"{prefix}{base}_{timestamp}{ext}"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            shutil.copy2(csv_path, backup_path)
            logger.info(f"Backed up dropzone order history file {os.path.basename(csv_path)} to {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup dropzone file {csv_path}: {e}")


def process_dropzone_files(optional_path=None):
    import shutil
    from src.services.brokerage_cache import BrokerageCache
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    target_path = optional_path if optional_path else os.path.join(project_root, "data", "dropzone")
    
    if os.path.isfile(target_path):
        all_files = [target_path]
        dropzone_dir = os.path.dirname(target_path)
    else:
        dropzone_dir = target_path
        archive_dir = os.path.abspath(os.path.join(dropzone_dir, "archive"))
        raw_files = glob.glob(os.path.join(dropzone_dir, "**", "*.csv"), recursive=True) + \
                    glob.glob(os.path.join(dropzone_dir, "**", "*.txt"), recursive=True)
        all_files = []
        for f in raw_files:
            if not os.path.abspath(f).startswith(archive_dir):
                all_files.append(f)
        all_files.sort(key=os.path.getctime, reverse=True)

    archive_dir = os.path.join(dropzone_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    
    # Load central configuration regexes
    config = get_config()
    dropzone_accounts = config.get("DROPZONE_ACCOUNTS", {})
        
    updates_made = False
    messages = []
    
    for file_path in all_files:
        filename = os.path.basename(file_path)
        lower_name = filename.lower()
        
        # Intercept empty 0-byte files
        if os.path.isfile(file_path) and os.path.getsize(file_path) == 0:
            dest_path = os.path.join(archive_dir, filename)
            try:
                shutil.copy2(file_path, dest_path)
                try:
                    os.remove(file_path)
                except Exception:
                    pass
                messages.append(f"Archived empty dropzone file: {filename}")
                updates_made = True
            except Exception as e:
                logger.error(f"Failed to archive empty file {file_path}: {e}")
            continue
            
        # Intercept color-coded watchlist files
        if "watchlist" in lower_name:
            from src.services.watchlist_db import (
                resolve_color_from_filename,
                resolve_date_from_filename,
                parse_watchlist_file,
                save_watchlist_entries
            )
            default_color = resolve_color_from_filename(filename)
            file_date = resolve_date_from_filename(filename, file_path)
            
            try:
                symbols_colors = parse_watchlist_file(file_path, default_color)
                if symbols_colors:
                    db_entries = []
                    imported_at_str = datetime.datetime.now().isoformat()
                    for sym, color in symbols_colors:
                        db_entries.append((file_date, color, sym, filename, imported_at_str))
                    save_watchlist_entries(db_entries)
                    
                    # Move processed file to archive
                    shutil.move(file_path, os.path.join(archive_dir, filename))
                    messages.append(f"Imported color-coded watchlist {filename} for {file_date} with {len(symbols_colors)} symbols.")
                    updates_made = True
                else:
                    logger.warning(f"No valid symbols parsed from watchlist file {filename}.")
            except Exception as e:
                logger.error(f"Failed to process watchlist file {filename}: {e}")
                messages.append(f"Error processing watchlist {filename}: {e}")
            continue
            
        # 1. Match exporting tool/account from subfolder path or config regexes
        target_account = None
        search_target = os.path.normpath(file_path)
        parent_folder = os.path.basename(os.path.dirname(file_path)).lower()

        if any(k in parent_folder for k in ["7328", "5972", "7952", "7925", "50287952"]):
            target_account = "TopStepX Express *7328"
        elif any(k in parent_folder for k in ["7085", "4889", "81134889"]):
            target_account = "TopStepX Combine *7085"
        elif "1299" in parent_folder:
            target_account = "TopStepX Combine *1299"
        elif "5496" in parent_folder:
            target_account = "TopStepX Combine *5496"
        elif "2210" in parent_folder:
            target_account = "TopStepX Express *2210"
        elif "topstep" in parent_folder:
            target_account = "TopStepX Express *2210"
        else:
            for acct, pattern in dropzone_accounts.items():
                try:
                    if re.search(pattern, filename, re.IGNORECASE) or re.search(pattern, search_target, re.IGNORECASE):
                        target_account = acct
                        break
                except Exception as e:
                    logger.error(f"Invalid regex '{pattern}' for account '{acct}': {e}")
                
        # Replay Trading Dropzone Ingestion Guard
        is_replay_trading = False
        replay_date_override = None
        if any(k in lower_name for k in ["replay trading", "replay_trading", "replay"]) or \
           any(k in search_target.lower() for k in ["replay trading", "replay_trading"]):
            is_replay_trading = True
        elif os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f_chk:
                    head_txt = f_chk.read(2048).lower()
                    if "replay trading" in head_txt or "replay_trading" in head_txt:
                        is_replay_trading = True
            except Exception:
                pass

        if is_replay_trading:
            date_match = re.search(r'(\d{4}[-_\.]\d{2}[-_\.]\d{2})|(\d{2}[-_\.]\d{2}[-_\.]\d{4})', filename)
            if date_match:
                raw_d = date_match.group(0).replace('_', '-').replace('.', '-')
                try:
                    if len(raw_d.split('-')[0]) == 4:
                        dt_obj = datetime.datetime.strptime(raw_d, "%Y-%m-%d")
                    else:
                        dt_obj = datetime.datetime.strptime(raw_d, "%m-%d-%Y")
                    replay_date_override = dt_obj.strftime("%Y-%m-%d")
                except Exception:
                    pass

            # Unified account for Replay Trades (supports both futures and equities)
            target_account = "Replay Trades"

        # Header fallback for TopStepX CSV exports
        if not target_account and os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as header_f:
                    first_line = header_f.readline()
                    if "ContractName" in first_line and "EnteredAt" in first_line and "ExitedAt" in first_line:
                        with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as full_f:
                            content = f"{search_target} {full_f.read()}".lower()
                        if "7328" in content or "5972" in content or "7952" in content or "7925" in content or "50287952" in content:
                            target_account = "TopStepX Express *7328"
                        elif "7085" in content or "4889" in content or "81134889" in content or "81137085" in content:
                            target_account = "TopStepX Combine *7085"
                        elif "1299" in content:
                            target_account = "TopStepX Combine *1299"
            except Exception:
                pass

        # If no regex match or header fallback is found, the file is unrecognized. Do not process it.
        if not target_account:
            logger.info(f"File {filename} does not match any regex mapping in DROPZONE_ACCOUNTS. Skipping.")
            continue
            
        # 2. Determine target tool and select appropriate parser
        parsed_data = {}
        file_type_label = ""
        paper_prefix = ""
        
        if is_replay_trading:
            paper_prefix = "REPLAY_"
            check_and_backup_dropzone_file(file_path, prefix=paper_prefix)
            
            is_topstep_fmt = False
            try:
                with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f_fmt:
                    line = f_fmt.readline()
                    if "ContractName" in line or "EnteredAt" in line:
                        is_topstep_fmt = True
            except Exception:
                pass

            if is_topstep_fmt:
                raw_parsed = parse_topstepx_trades(file_path)
                parsed_data = {}
                if isinstance(raw_parsed, dict):
                    acts = raw_parsed.get("activities", {})
                    cls_pos = raw_parsed.get("closed_positions", {})
                    all_acts = []
                    for data_list in acts.values():
                        all_acts.extend(data_list)
                    all_cls = []
                    for data_list in cls_pos.values():
                        all_cls.extend(data_list)
                    parsed_data = {
                        "activities": {target_account: all_acts},
                        "closed_positions": {target_account: all_cls}
                    }
            else:
                is_strategy_report = False
                try:
                    with open(file_path, "r", encoding="utf-8-sig", errors="ignore") as f_rpt:
                        hdr = f_rpt.readline()
                        if "Trade number" in hdr or "Trade #" in hdr or "Net PnL" in hdr or "Favorable excursion" in hdr:
                            is_strategy_report = True
                except Exception:
                    pass

                if is_strategy_report:
                    parsed_data = parse_tradingview_replay_report(file_path)
                else:
                    raw_parsed = parse_tradingview_paper_trading(file_path)
                    all_acts = []
                    if isinstance(raw_parsed, dict):
                        for data_list in raw_parsed.values():
                            all_acts.extend(data_list)
                    parsed_data = {target_account: all_acts}
                
            file_type_label = f"Replay Trading ({target_account})"

            # Only rebind dates if the parsed trades do not already contain explicit replay row timestamps
            if replay_date_override and parsed_data and not is_strategy_report:
                def rebind_dates(item_list):
                    for item in item_list:
                        if isinstance(item, dict):
                            for d_key in ["trade_date", "close_date", "open_date"]:
                                if d_key in item and item[d_key]:
                                    val = str(item[d_key])
                                    t_part = "09:30:00.000Z"
                                    if "T" in val:
                                        t_part = val.split("T")[-1]
                                    elif " " in val:
                                        t_part = val.split(" ")[-1]
                                    item[d_key] = f"{replay_date_override}T{t_part}"

                if "activities" in parsed_data:
                    for acct, act_list in parsed_data["activities"].items():
                        rebind_dates(act_list)
                if "closed_positions" in parsed_data:
                    for acct, pos_list in parsed_data["closed_positions"].items():
                        rebind_dates(pos_list)
                if isinstance(parsed_data, dict):
                    for acct, act_list in parsed_data.items():
                        if isinstance(act_list, list):
                            rebind_dates(act_list)

        elif "topstep" in target_account.lower() or "topstep" in lower_name or "topstep" in search_target.lower():
            paper_prefix = "TOPSTEP_"
            check_and_backup_dropzone_file(file_path, prefix=paper_prefix)
            parsed_data = parse_topstepx_trades(file_path)
            file_type_label = ", ".join(parsed_data.keys()) if parsed_data else target_account
        elif "paper" in target_account.lower():
            # TradingView Paper Trading export
            asset_type = get_tradingview_csv_asset_type(file_path)
            if asset_type:
                paper_prefix = f"{asset_type}_"
            
            # Map generic/specific TradingView accounts based on asset type check
            if asset_type == "STOCKS":
                target_account = "TradingView Paper Stocks"
            elif asset_type == "FUTURES":
                target_account = "TradingView Paper Futures"
                
            check_and_backup_dropzone_file(file_path, prefix=paper_prefix)
            parsed_data = parse_tradingview_paper_trading(file_path)
            file_type_label = ", ".join(parsed_data.keys()) if parsed_data else target_account
        else:
            # Fidelity export. Determine specific Fidelity export type from filename.
            if "closed_positions" in lower_name or "closed-positions" in lower_name:
                parsed_data = parse_fidelity_closed_positions(file_path)
                file_type_label = "Closed Positions"
                # Override to matched Fidelity account
                if parsed_data:
                    all_data = []
                    for data_list in parsed_data.values():
                        all_data.extend(data_list)
                    parsed_data = {target_account: all_data}
            elif "positions" in lower_name:
                parsed_data = parse_fidelity_positions(file_path)
                file_type_label = "Positions"
                if parsed_data:
                    all_data = []
                    for data_list in parsed_data.values():
                        all_data.extend(data_list)
                    parsed_data = {target_account: all_data}
            elif "orders" in lower_name:
                check_and_backup_dropzone_file(file_path)
                parsed_data = parse_fidelity_orders(file_path)
                file_type_label = "Orders"
                if parsed_data:
                    all_data = []
                    for data_list in parsed_data.values():
                        all_data.extend(data_list)
                    parsed_data = {target_account: all_data}
            elif "history" in lower_name or "activity" in lower_name:
                parsed_data = parse_fidelity_history(file_path)
                file_type_label = "History"
                if parsed_data:
                    all_data = []
                    for data_list in parsed_data.values():
                        all_data.extend(data_list)
                    parsed_data = {target_account: all_data}
            else:
                logger.info(f"Fidelity file {filename} does not match any expected export type keyword (orders, history, activity, positions). Skipping.")
                continue
                
        # 3. Merge parsed details to cache and move file to archive
        file_updated = False
        if isinstance(parsed_data, dict) and ("activities" in parsed_data or "closed_positions" in parsed_data):
            for account, data in parsed_data.get("activities", {}).items():
                if data:
                    BrokerageCache.merge_activities(account, data)
                    file_updated = True
                    updates_made = True
            for account, data in parsed_data.get("closed_positions", {}).items():
                if data:
                    BrokerageCache.replace_closed_positions(account, data)
                    file_updated = True
                    updates_made = True
        else:
            for account, data in parsed_data.items():
                if not data:
                    continue
                if "paper" in file_type_label.lower() or "topstep" in file_type_label.lower() or file_type_label in ["Orders", "History"]:
                    BrokerageCache.merge_activities(account, data)
                    file_updated = True
                    updates_made = True
                elif file_type_label == "Positions":
                    BrokerageCache.set_positions(account, data)
                    file_updated = True
                    updates_made = True
                elif file_type_label == "Closed Positions":
                    BrokerageCache.replace_closed_positions(account, data)
                    file_updated = True
                    updates_made = True
                
        if file_updated or (target_account and "paper" in target_account.lower()):
            parent_dir = os.path.basename(os.path.dirname(file_path))
            subfolder_prefix = f"{parent_dir}_" if (parent_dir and parent_dir != os.path.basename(dropzone_dir) and parent_dir != "archive") else ""
            dest_filename = f"{paper_prefix}{subfolder_prefix}{filename}" if (paper_prefix and not filename.startswith(paper_prefix)) else f"{subfolder_prefix}{filename}"
            dest_path = os.path.join(archive_dir, dest_filename)
            try:
                shutil.copy2(file_path, dest_path)
                try:
                    os.remove(file_path)
                except Exception as rem_err:
                    logger.warning(f"Copied dropzone file {filename} to archive, but could not remove original: {rem_err}")
                messages.append(f"Imported {file_type_label or target_account}: {dest_filename}")
                updates_made = True
            except Exception as e:
                logger.error(f"Failed to archive {file_path}: {e}")
                messages.append(f"Imported {file_type_label or target_account} (failed to archive): {filename}")
                
    if updates_made:
        from src.tools.broker import export_to_tradezella
        try:
            export_to_tradezella.invoke({"timeframe": "day"}, config=None)
            messages.append("TradeZella export updated successfully.")
        except Exception as e:
            messages.append(f"Failed to trigger TradeZella export: {e}")
            logger.error(f"TradeZella export failed during dropzone processing: {e}")

        try:
            import subprocess
            import sys
            script_path = os.path.join(project_root, "scripts", "utils", "generate_tradingview_script.py")
            creationflags = subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0
            subprocess.run([sys.executable, script_path], check=True, capture_output=True, creationflags=creationflags)
            messages.append("TradingView script updated successfully.")
        except Exception as tv_err:
            logger.error(f"TradingView script generation failed during dropzone processing: {tv_err}")
            messages.append(f"Warning: Failed to generate TradingView script: {tv_err}")

    if not messages:
        return "No valid CSVs found to process."
        
    return "\n".join(messages)


# Backwards compatibility legacy aliases
parse_atp_orders = parse_fidelity_orders
parse_atp_history = parse_fidelity_history
parse_atp_positions = parse_fidelity_positions
parse_atp_closed_positions = parse_fidelity_closed_positions

_last_dropzone_files = None

def watch_dropzone_and_process(optional_path=None):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dropzone_dir = optional_path if optional_path else os.path.join(project_root, "data", "dropzone")
    
    if not os.path.exists(dropzone_dir):
        return "Dropzone directory not found."

    try:
        if os.path.isfile(dropzone_dir):
            current_files = [dropzone_dir]
        else:
            archive_dir = os.path.abspath(os.path.join(dropzone_dir, "archive"))
            raw_files = glob.glob(os.path.join(dropzone_dir, "**", "*.csv"), recursive=True) + \
                        glob.glob(os.path.join(dropzone_dir, "**", "*.txt"), recursive=True)
            current_files = [f for f in raw_files if not os.path.abspath(f).startswith(archive_dir)]
            
        if current_files:
            logger.info(f"Dropzone files detected: {[os.path.basename(f) for f in current_files]}. Processing.")
            return process_dropzone_files(optional_path)
            
        return "No files to process in dropzone folder."
    except Exception as e:
        logger.error(f"Error in watch_dropzone_and_process: {e}")
        return f"Error: {e}"

