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
        
    activities = []
    
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            status = row.get("Status") or ""
            if status != "Filled":
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
            
            # Format closing time to ISO string
            try:
                dt_obj = datetime.datetime.strptime(closing_time, "%Y-%m-%d %H:%M:%S")
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
            activities.append(activity)
            
    # Try to determine target account from DROPZONE_ACCOUNTS config mapping
    target_account = "TradingView Paper Stocks"  # default fallback
    try:
        config = get_config()
        dropzone_accounts = config.get("DROPZONE_ACCOUNTS", {})
        filename = os.path.basename(csv_path)
        for acct, pattern in dropzone_accounts.items():
            if "paper" in acct.lower() and re.match(pattern, filename):
                target_account = acct
                break
    except Exception as e:
        logger.error(f"Error resolving target account in parse_tradingview_paper_trading: {e}")
        
    return {target_account: activities}


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

def check_and_backup_dropzone_file(csv_path: str):
    if not csv_path or not os.path.exists(csv_path):
        return
        
    contains_date_time = False
    try:
        with open(csv_path, 'r', encoding='utf-8-sig', errors='ignore') as f:
            first_lines = "".join([f.readline() for _ in range(50)])
            if "Order Time" in first_lines or ("Date" in first_lines and "Time" in first_lines) or "Closing time" in first_lines:
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
            backup_filename = f"{base}_{timestamp}{ext}"
            backup_path = os.path.join(backup_dir, backup_filename)
            
            shutil.copy2(csv_path, backup_path)
            logger.info(f"Backed up dropzone order history file {os.path.basename(csv_path)} to {backup_path}")
        except Exception as e:
            logger.error(f"Failed to backup dropzone file {csv_path}: {e}")


def process_dropzone_files(optional_path=None):
    import shutil
    from src.services.brokerage_cache import BrokerageCache
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dropzone_dir = optional_path if optional_path else os.path.join(project_root, "data", "dropzone")
    archive_dir = os.path.join(dropzone_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    
    # Load central configuration regexes
    config = get_config()
    dropzone_accounts = config.get("DROPZONE_ACCOUNTS", {})
    
    if os.path.isfile(dropzone_dir):
        all_files = [dropzone_dir]
    else:
        all_files = glob.glob(os.path.join(dropzone_dir, "*.csv")) + glob.glob(os.path.join(dropzone_dir, "*.txt"))
        all_files.sort(key=os.path.getctime, reverse=True)
        
    updates_made = False
    messages = []
    
    for file_path in all_files:
        filename = os.path.basename(file_path)
        lower_name = filename.lower()
        
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
            
        # 1. Match exporting tool/account from config regexes
        target_account = None
        for acct, pattern in dropzone_accounts.items():
            try:
                if re.match(pattern, filename):
                    target_account = acct
                    break
            except Exception as e:
                logger.error(f"Invalid regex '{pattern}' for account '{acct}': {e}")
                
        # If no regex match is found, the file is unrecognized. Do not process it.
        if not target_account:
            logger.info(f"File {filename} does not match any regex mapping in DROPZONE_ACCOUNTS. Skipping.")
            continue
            
        # 2. Determine target tool and select appropriate parser
        parsed_data = {}
        file_type_label = ""
        
        if "paper" in target_account.lower():
            # TradingView Paper Trading export
            check_and_backup_dropzone_file(file_path)
            parsed_data = parse_tradingview_paper_trading(file_path)
            if parsed_data:
                parsed_data = {target_account: list(parsed_data.values())[0]}
            file_type_label = target_account
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
        for account, data in parsed_data.items():
            if not data:
                continue
            if "paper" in file_type_label.lower() or file_type_label in ["Orders", "History"]:
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
                
        if file_updated:
            try:
                shutil.move(file_path, os.path.join(archive_dir, filename))
                messages.append(f"Imported {file_type_label}: {filename}")
            except Exception as e:
                logger.error(f"Failed to archive {file_path}: {e}")
                messages.append(f"Imported {file_type_label} (failed to archive): {filename}")
                
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
            script_path = os.path.join(project_root, "scripts", "utils", "generate_tradingview_script.py")
            subprocess.run(["python", script_path], check=True, capture_output=True)
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
    global _last_dropzone_files
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dropzone_dir = optional_path if optional_path else os.path.join(project_root, "data", "dropzone")
    
    if not os.path.exists(dropzone_dir):
        return "Dropzone directory not found."
        
    try:
        if os.path.isfile(dropzone_dir):
            current_files = {os.path.basename(dropzone_dir)}
        else:
            current_files = {os.path.basename(f) for f in glob.glob(os.path.join(dropzone_dir, "*.csv")) + glob.glob(os.path.join(dropzone_dir, "*.txt"))}
            
        if _last_dropzone_files is None:
            # Initialize on first run
            _last_dropzone_files = current_files
            # Run once to process any existing files
            if current_files:
                return process_dropzone_files(optional_path)
            return "No files to process on initial run."
            
        if current_files != _last_dropzone_files:
            logger.info(f"Dropzone directory change detected. Files changed from {_last_dropzone_files} to {current_files}. Processing.")
            _last_dropzone_files = current_files
            return process_dropzone_files(optional_path)
            
        return "No changes in dropzone folder."
    except Exception as e:
        logger.error(f"Error in watch_dropzone_and_process: {e}")
        return f"Error: {e}"

