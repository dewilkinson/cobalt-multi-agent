import csv
import os

activity_path = "data/dropzone/archive/Activity_All_Accounts.csv"
if not os.path.exists(activity_path):
    print("Activity file not found!")
    exit(1)

with open(activity_path, 'r', encoding='utf-8') as f:
    lines = f.readlines()

header_idx = -1
for i, line in enumerate(lines):
    if line.startswith("Description,Symbol,Quantity"):
        header_idx = i
        break

if header_idx == -1:
    print("Could not find headers!")
    print("First 5 lines of file:")
    for line in lines[:5]:
        print(repr(line))
    exit(1)

print(f"Headers found at line {header_idx + 1}")
csv_data = "".join(lines[header_idx:])
reader = csv.DictReader(csv_data.splitlines())

dates = set()
symbols = set()
rows_count = 0
for row in reader:
    rows_count += 1
    dates.add(row.get("Settlement Date"))
    symbols.add(row.get("Symbol"))

print(f"Total rows: {rows_count}")
clean_dates = sorted([str(d) for d in dates if d is not None])
print(f"Unique settlement dates: {clean_dates}")
print(f"Unique symbols: {sorted([str(s) for s in symbols if s])}")
