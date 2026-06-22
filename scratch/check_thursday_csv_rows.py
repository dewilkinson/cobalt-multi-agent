import csv
import os

csv_path = "data/exports/tradezella-import-this-week.csv"
if not os.path.exists(csv_path):
    print("CSV not found!")
    exit(1)

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

thursday_rows = [r for r in rows if r.get("Date") == "05/21/2026"]
print(f"Total rows for Thursday 05/21/2026: {len(thursday_rows)}")
for r in thursday_rows:
    print(f"  Account: {r['Account Name']} | Time: {r['Time']} | Symbol: {r['Symbol']} | Action: {r['Buy/Sell']} | Qty: {r['Quantity']} | Price: {r['Price']}")
