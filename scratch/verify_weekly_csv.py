import csv
import os

csv_path = "data/exports/tradezella-import-this-week.csv"
if not os.path.exists(csv_path):
    print("CSV not found!")
    exit(1)

with open(csv_path, 'r', encoding='utf-8') as f:
    reader = csv.DictReader(f)
    rows = list(reader)

print(f"Total rows in TradeZella CSV: {len(rows)}")

# Count trades per date
trades_by_date = {}
for row in rows:
    date = row.get("Date")
    trades_by_date[date] = trades_by_date.get(date, 0) + 1

for date in sorted(trades_by_date.keys()):
    print(f"  {date}: {trades_by_date[date]} trades")

# Print first few rows of May 19 to confirm contents
print("\nFirst 5 trades on May 19:")
may19_trades = [r for r in rows if r.get("Date") == "05/19/2026"]
for r in may19_trades[:5]:
    print(f"  Account: {r['Account Name']} | Time: {r['Time']} | Symbol: {r['Symbol']} | Action: {r['Buy/Sell']} | Qty: {r['Quantity']} | Price: {r['Price']}")
