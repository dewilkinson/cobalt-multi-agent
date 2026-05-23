import json
import csv
from collections import defaultdict
from datetime import datetime, timedelta
import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
cache_path = os.path.join(BASE_DIR, "data", "brokerage_cache.json")
output_path = os.path.join(BASE_DIR, "data", "exports", "tradezella-import-20260401-20260516.csv")

def process(start_date="2026-04-01", end_date="2026-05-16"):
    output_path = os.path.join(BASE_DIR, "data", "exports", f"tradezella-import-{start_date.replace('-','')}-{end_date.replace('-','')}.csv")
    
    with open(cache_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    trades_to_export = []
    
    for account_name, account_data in data.items():
        if account_name != "Rollover IRA *5513":
            continue
        if "activities" not in account_data: continue
        
        all_activities = []
        for activity in account_data["activities"]:
            if activity.get("status") != "Executed": continue
            if not activity.get("trade_date"): continue
            all_activities.append(activity)
            
        all_activities.sort(key=lambda x: x.get("trade_date", ""))
        
        deduped = []
        for act in all_activities:
            dt_str = act.get("trade_date", "")
            fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in dt_str else "%Y-%m-%dT%H:%M:%SZ"
            try:
                dt = datetime.strptime(dt_str, fmt)
            except: continue
                
            sym = act["symbol"]["symbol"]
            action = act.get("type", "").lower()
            qty = float(act["units"])
            price = float(act["price"])
            
            is_dup = False
            for prev in reversed(deduped[-10:]):
                if prev["symbol"]["symbol"] == sym and prev.get("type", "").lower() == action and float(prev["units"]) == qty and abs(float(prev["price"]) - price) < 0.001:
                    prev_dt_str = prev.get("trade_date", "")
                    prev_fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in prev_dt_str else "%Y-%m-%dT%H:%M:%SZ"
                    prev_dt = datetime.strptime(prev_dt_str, prev_fmt)
                    if abs((dt - prev_dt).total_seconds()) <= 300:
                        is_dup = True
                        break
            if not is_dup:
                deduped.append(act)
                
        # Split into pre and window
        pre_acts = []
        win_acts = []
        for act in deduped:
            date_part = act.get("trade_date", "")[:10]
            if date_part < start_date:
                pre_acts.append(act)
            elif start_date <= date_part <= end_date:
                win_acts.append(act)
                
        # Calculate pre_net_pos for all symbols
        pre_net_pos = defaultdict(float)
        for act in pre_acts:
            sym = act["symbol"]["symbol"]
            q = float(act["units"])
            if act.get("type", "").lower() == "buy":
                pre_net_pos[sym] += q
            elif act.get("type", "").lower() == "sell":
                pre_net_pos[sym] -= q
                
        running_pos = defaultdict(float)
        
        # We will iterate through window_acts.
        final_window_acts = []
        
        for act in win_acts:
            sym = act["symbol"]["symbol"]
            action = act.get("type", "").lower()
            q = float(act["units"])
            
            dt_str = act.get("trade_date", "")
            fmt = "%Y-%m-%dT%H:%M:%S.%fZ" if "." in dt_str else "%Y-%m-%dT%H:%M:%SZ"
            try:
                dt = datetime.strptime(dt_str, fmt)
            except:
                dt = datetime.strptime(dt_str, "%Y-%m-%dT%H:%M:%SZ")
                
            if action == "buy":
                running_pos[sym] += q
                final_window_acts.append({
                    "Account Name": account_name,
                    "Date&Time": "",
                    "Date": dt.strftime("%m/%d/%Y"),
                    "Time": dt.strftime("%H:%M:%S"),
                    "Symbol": sym,
                    "Buy/Sell": "Buy",
                    "Quantity": int(q) if q.is_integer() else q,
                    "Price": float(act["price"]),
                    "Spread": "Stock",
                    "Expiration": "", "Strike": "", "Call/Put": "", "Commission": 0, "Fees": 0,
                    "_dt": dt
                })
            elif action == "sell":
                # Check if we have enough shares
                if running_pos[sym] < q:
                    deficit = q - running_pos[sym]
                    
                    # We need to inject a dummy buy for `deficit` shares right before this sell.
                    # Price it using history if available, else use this sell's price
                    fallback_price = float(act["price"])
                    
                    total_cost = 0.0
                    shares_priced = 0.0
                    
                    if pre_net_pos[sym] > 0:
                        avail = min(pre_net_pos[sym], deficit)
                        # look backwards in pre_acts
                        pre_buys = [a for a in pre_acts if a["symbol"]["symbol"] == sym and a.get("type","").lower()=="buy"]
                        pre_buys.sort(key=lambda x: x.get("trade_date",""), reverse=True)
                        shares_found = 0.0
                        for b in pre_buys:
                            b_qty = float(b["units"])
                            b_price = float(b["price"])
                            needed = avail - shares_found
                            if needed <= 0: break
                            take = min(b_qty, needed)
                            total_cost += take * b_price
                            shares_found += take
                        shares_priced = shares_found
                        pre_net_pos[sym] -= shares_priced # Consume these historical shares
                        
                    rem_deficit = deficit - shares_priced
                    total_cost += rem_deficit * fallback_price
                    
                    avg_price = total_cost / deficit if deficit > 0 else fallback_price
                    
                    dummy_dt = dt
                    final_window_acts.append({
                        "Account Name": account_name,
                        "Date&Time": "",
                        "Date": dummy_dt.strftime("%m/%d/%Y"),
                        "Time": dummy_dt.strftime("%H:%M:%S"),
                        "Symbol": sym,
                        "Buy/Sell": "Buy",
                        "Quantity": int(deficit) if float(deficit).is_integer() else deficit,
                        "Price": round(avg_price, 4),
                        "Spread": "Stock",
                        "Expiration": "", "Strike": "", "Call/Put": "", "Commission": 0, "Fees": 0,
                        "_dt": dummy_dt
                    })
                    
                    running_pos[sym] += deficit
                
                running_pos[sym] -= q
                final_window_acts.append({
                    "Account Name": account_name,
                    "Date&Time": "",
                    "Date": dt.strftime("%m/%d/%Y"),
                    "Time": dt.strftime("%H:%M:%S"),
                    "Symbol": sym,
                    "Buy/Sell": "Sell",
                    "Quantity": int(q) if q.is_integer() else q,
                    "Price": float(act["price"]),
                    "Spread": "Stock",
                    "Expiration": "", "Strike": "", "Call/Put": "", "Commission": 0, "Fees": 0,
                    "_dt": dt
                })
                
        trades_to_export.extend(final_window_acts)

    # Sort chronological
    trades_to_export.sort(key=lambda x: (x["_dt"], x["Symbol"], 0 if x["Buy/Sell"] == "Buy" else 1))
    
    current_date = None
    time_offset_seconds = 0
    
    for row in trades_to_export:
        if row["Time"] == "00:00:00":
            if row["Date"] != current_date:
                current_date = row["Date"]
                time_offset_seconds = 0
            base_time = datetime.strptime("09:30:00", "%H:%M:%S")
            new_time = base_time + timedelta(seconds=time_offset_seconds)
            row["Time"] = new_time.strftime("%H:%M:%S")
            time_offset_seconds += 300
            
        del row["_dt"]
        
    tz_headers = ["Account Name", "Date&Time", "Date", "Time", "Symbol", "Buy/Sell", "Quantity", "Price", "Spread", "Expiration", "Strike", "Call/Put", "Commission", "Fees"]
    
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers)
        writer.writeheader()
        writer.writerows(trades_to_export)
        
    print(f"Success! {len(trades_to_export)} trades exported.")

if __name__ == "__main__":
    import sys
    start = sys.argv[1] if len(sys.argv) > 1 else "2026-04-01"
    end = sys.argv[2] if len(sys.argv) > 2 else "2026-05-16"
    process(start, end)
