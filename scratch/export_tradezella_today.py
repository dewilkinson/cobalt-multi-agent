import json
import csv
from datetime import datetime
import os

cache_path = "data/archive/BrokerageCacheDailyBackup_2026-06-04.json"
output_path = "data/exports/tradezella-import.csv"

def extract_trades():
    print(f"Reading from {cache_path}...")
    with open(cache_path, 'r', encoding='utf-8') as f:
        data = json.load(f)
        
    trades_to_export = []
    
    for account_name, account_data in data.items():
        if "activities" in account_data:
            for activity in account_data["activities"]:
                if activity.get("status") != "Executed":
                    continue
                
                # Check if it executed today (2026-06-04)
                trade_date_str = activity.get("trade_date", "")
                if not trade_date_str or not trade_date_str.startswith("2026-06-04"):
                    continue
                
                # Parse timestamp safely
                clean_str = trade_date_str.replace("Z", "")
                if "." in clean_str:
                    parts = clean_str.split(".")
                    clean_str = parts[0] + "." + parts[1][:6]
                    dt = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S.%f")
                else:
                    dt = datetime.strptime(clean_str, "%Y-%m-%dT%H:%M:%S")
                    
                tz_date = dt.strftime("%m/%d/%Y")
                tz_time = dt.strftime("%H:%M:%S")
                
                action = activity.get("type", "").capitalize()
                
                # Resolve symbol
                sym_data = activity.get("symbol", {})
                if isinstance(sym_data, dict):
                    sym = sym_data.get("symbol", "")
                else:
                    sym = str(sym_data)
                
                trades_to_export.append({
                    "Account Name": account_name,
                    "Date&Time": "",
                    "Date": tz_date,
                    "Time": tz_time,
                    "Symbol": sym.upper(),
                    "Buy/Sell": action,
                    "Quantity": float(activity["units"]),
                    "Price": float(activity["price"]),
                    "Spread": "Stock",
                    "Expiration": "",
                    "Strike": "",
                    "Call/Put": "",
                    "Commission": 0,
                    "Fees": 0
                })
                
    # Sort chronological: Date -> Time -> Symbol -> Action (Buy before Sell)
    trades_to_export.sort(key=lambda x: (x["Date"], x["Time"], x["Symbol"], 0 if x["Buy/Sell"].lower() == "buy" else 1))
    
    # Write to CSV
    tz_headers = ["Account Name", "Date&Time", "Date", "Time", "Symbol", "Buy/Sell", "Quantity", "Price", "Spread", "Expiration", "Strike", "Call/Put", "Commission", "Fees"]
    
    os.makedirs(os.path.dirname(output_path), exist_ok=True)
    with open(output_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=tz_headers)
        writer.writeheader()
        writer.writerows(trades_to_export)
        
    print(f"Success! {len(trades_to_export)} trades exported to {output_path}")

if __name__ == "__main__":
    extract_trades()
