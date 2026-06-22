import os
import csv

dropzone_dir = "data/dropzone"

def scan_file(file_path):
    print(f"\nScanning: {file_path}")
    with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
        lines = f.readlines()
        
    header_idx = -1
    for i, line in enumerate(lines):
        if "Description" in line or "Symbol" in line or "Quantity" in line:
            header_idx = i
            break
            
    if header_idx == -1:
        # Just search for "19" in raw text if headers not found
        raw_text = "".join(lines)
        if "2026-05-19" in raw_text or "05/19/2026" in raw_text or "May-19" in raw_text:
            print("  -> Found May 19 in raw text!")
        else:
            print("  -> No headers, no May 19 in raw text.")
        return
        
    csv_data = "".join(lines[header_idx:])
    try:
        reader = csv.DictReader(csv_data.splitlines())
        dates = set()
        rows_count = 0
        for row in reader:
            rows_count += 1
            for k, v in row.items():
                if k and any(term in k for term in ["Date", "Time", "Settlement"]):
                    if v:
                        dates.add(str(v).strip())
        
        print(f"  Total rows parsed: {rows_count}")
        may19_matches = [d for d in dates if "19" in d and ("2026" in d or "May" in d or d.startswith("05"))]
        if may19_matches:
            print(f"  -> FOUND MAY 19 matches: {may19_matches}")
        else:
            # Let's print some sample dates
            sample_dates = sorted(list(dates))[:10]
            print(f"  No May 19 found. Sample dates found: {sample_dates}")
    except Exception as e:
        print(f"  Error parsing CSV: {e}")

for root, dirs, files in os.walk(dropzone_dir):
    for file in files:
        if file.lower().endswith('.csv'):
            scan_file(os.path.join(root, file))
