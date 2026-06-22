import os
import csv
from datetime import datetime

files_to_check = [
    "data/dropzone/Activity_2026.csv",
    "data/dropzone/Activity_Rollover_IRA__5513.csv",
    "data/dropzone/YTD.csv"
]

for file_path in files_to_check:
    if not os.path.exists(file_path):
        print(f"{file_path} does not exist.")
        continue
    print(f"\nAnalyzing: {file_path}")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    header_idx = -1
    for i, line in enumerate(lines):
        if "Description" in line or "Symbol" in line or "Quantity" in line:
            header_idx = i
            break
            
    if header_idx == -1:
        print("  Headers not found.")
        continue
        
    csv_data = "".join(lines[header_idx:])
    reader = csv.DictReader(csv_data.splitlines())
    dates = []
    may_2026_dates = set()
    for row in reader:
        for k, v in row.items():
            if k and any(term in k for term in ["Date", "Time", "Settlement"]):
                if v and v.strip() not in ["", "--"]:
                    val = v.strip()
                    dates.append(val)
                    if "May" in val and "2026" in val:
                        may_2026_dates.add(val)
                    elif val.startswith("05/") and val.endswith("/2026"):
                        may_2026_dates.add(val)
                        
    if dates:
        print(f"  Total date values: {len(dates)}")
        print(f"  May 2026 dates found: {sorted(list(may_2026_dates))}")
        # Print a few samples from start and end
        print(f"  Sample values: {dates[:5]} ... {dates[-5:]}")
    else:
        print("  No valid dates found.")
