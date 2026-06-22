import os
import glob
from datetime import datetime

search_paths = [
    "C:/Users/rende/Downloads",
    "C:/Users/rende/Desktop",
    "C:/Users/rende/Documents",
    "C:/Users/rende/OneDrive"
]

print("Listing all recent CSV/HTML files...")
for base_path in search_paths:
    if not os.path.exists(base_path):
        continue
    print(f"\n--- Checking {base_path} ---")
    for ext in ["*.csv", "*.html", "*.txt"]:
        pattern = os.path.join(base_path, "**", ext)
        try:
            for file_path in glob.glob(pattern, recursive=True):
                try:
                    mtime = os.path.getmtime(file_path)
                    dt_m = datetime.fromtimestamp(mtime)
                    if dt_m.year == 2026 and dt_m.month == 5 and (15 <= dt_m.day <= 23):
                        print(f"{file_path} | Modified: {dt_m} | Size: {os.path.getsize(file_path)} bytes")
                except Exception:
                    pass
        except Exception:
            pass
