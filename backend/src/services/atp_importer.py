import os
import csv
import io
import datetime
import glob
import logging

logger = logging.getLogger(__name__)

def parse_atp_orders(csv_path: str):
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

def parse_atp_history(csv_path: str):
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

def parse_atp_positions(csv_path: str):
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

def parse_atp_closed_positions(csv_path: str):
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


def get_dropzone_csvs(optional_path=None):
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    search_dir = optional_path if optional_path else os.path.join(project_root, "data", "dropzone")
    csvs = {"orders": None, "history": None, "positions": None, "closed_positions": None}
    
    if os.path.isfile(search_dir) and search_dir.endswith('.csv'):
        all_csvs = [search_dir]
    else:
        all_csvs = glob.glob(os.path.join(search_dir, "*.csv"))
        all_csvs.sort(key=os.path.getctime, reverse=True)
    
    for c in all_csvs:
        lower_name = os.path.basename(c).lower()
        if "orders" in lower_name and not csvs["orders"]:
            csvs["orders"] = c
        elif ("history" in lower_name or "activity" in lower_name) and not csvs["history"]:
            csvs["history"] = c
        elif "positions" in lower_name and "closed" not in lower_name and not csvs["positions"]:
            csvs["positions"] = c
        elif "closed_positions" in lower_name and not csvs["closed_positions"]:
            csvs["closed_positions"] = c
            
    return csvs

def process_dropzone_files(optional_path=None):
    import shutil
    from src.services.brokerage_cache import BrokerageCache
    
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    dropzone_dir = os.path.join(project_root, "data", "dropzone")
    archive_dir = os.path.join(dropzone_dir, "archive")
    os.makedirs(archive_dir, exist_ok=True)
    
    csvs = get_dropzone_csvs(optional_path)
    
    updates_made = False
    messages = []
    
    # Process History
    if csvs["history"]:
        history_data = parse_atp_history(csvs["history"])
        for account, acts in history_data.items():
            if acts:
                BrokerageCache.merge_activities(account, acts)
                updates_made = True
        try:
            shutil.move(csvs["history"], os.path.join(archive_dir, os.path.basename(csvs["history"])))
            messages.append(f"Imported History: {os.path.basename(csvs['history'])}")
        except Exception as e:
            logger.error(f"Failed to archive {csvs['history']}: {e}")
            messages.append(f"Imported History (failed to archive): {os.path.basename(csvs['history'])}")
        
    # Process Orders
    if csvs["orders"]:
        orders_data = parse_atp_orders(csvs["orders"])
        for account, acts in orders_data.items():
            if acts:
                BrokerageCache.merge_activities(account, acts)
                updates_made = True
        try:
            shutil.move(csvs["orders"], os.path.join(archive_dir, os.path.basename(csvs["orders"])))
            messages.append(f"Imported Orders: {os.path.basename(csvs['orders'])}")
        except Exception as e:
            logger.error(f"Failed to archive {csvs['orders']}: {e}")
            messages.append(f"Imported Orders (failed to archive): {os.path.basename(csvs['orders'])}")
        
    # Process Positions
    if csvs["positions"]:
        positions_data = parse_atp_positions(csvs["positions"])
        for account, pos_list in positions_data.items():
            if pos_list:
                BrokerageCache.set_positions(account, pos_list)
                updates_made = True
        try:
            shutil.move(csvs["positions"], os.path.join(archive_dir, os.path.basename(csvs["positions"])))
            messages.append(f"Imported Positions: {os.path.basename(csvs['positions'])}")
        except Exception as e:
            logger.error(f"Failed to archive {csvs['positions']}: {e}")
            messages.append(f"Imported Positions (failed to archive): {os.path.basename(csvs['positions'])}")

    # Process Closed Positions
    if csvs["closed_positions"]:
        closed_data = parse_atp_closed_positions(csvs["closed_positions"])
        for account, cp in closed_data.items():
            if cp:
                BrokerageCache.replace_closed_positions(account, cp)
                updates_made = True
        try:
            shutil.move(csvs["closed_positions"], os.path.join(archive_dir, os.path.basename(csvs["closed_positions"])))
            messages.append(f"Imported Closed Positions: {os.path.basename(csvs['closed_positions'])}")
        except Exception as e:
            logger.error(f"Failed to archive {csvs['closed_positions']}: {e}")
            messages.append(f"Imported Closed Positions (failed to archive): {os.path.basename(csvs['closed_positions'])}")

    if updates_made:
        from src.tools.broker import export_to_tradezella
        try:
            # Re-export to TradeZella after cache updates
            export_to_tradezella.invoke({"timeframe": "day"}, config=None)
            messages.append("TradeZella export updated successfully.")
        except Exception as e:
            messages.append(f"Failed to trigger TradeZella export: {e}")
            logger.error(f"TradeZella export failed during dropzone processing: {e}")

    if not messages:
        return "No valid CSVs found to process."
        
    return "\n".join(messages)
