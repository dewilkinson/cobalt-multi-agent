import csv
import os

orders_path = "data/dropzone/archive/Orders_Rollover_IRA__5513.csv"
if not os.path.exists(orders_path):
    print("Orders file not found!")
    exit(1)

with open(orders_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

header_idx = -1
for i, line in enumerate(lines):
    if line.startswith("Symbol,Action,Amount"):
        header_idx = i
        break

if header_idx == -1:
    print("Headers not found.")
    exit(1)

csv_data = "".join(lines[header_idx:])
reader = csv.DictReader(csv_data.splitlines())

print("May 21 Orders:")
for row in reader:
    sym = row.get("Symbol")
    action = row.get("Action")
    qty = row.get("Amount")
    status = row.get("Status")
    time_str = row.get("Order Time")
    print(f"  Symbol: {sym} | Action: {action} | Qty: {qty} | Status: {status} | Time: {time_str}")
