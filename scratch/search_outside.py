import os
import glob
from datetime import datetime

search_paths = [
    "C:/Users/rende/Downloads",
    "C:/Users/rende/Documents",
    "C:/Users/rende/Desktop",
    "C:/Users/rende/OneDrive",
    "C:/Users/rende/obsidian-vault"
]

print("Searching for trade files outside workspace...")
found_files = []

for base_path in search_paths:
    if not os.path.exists(base_path):
        continue
    print(f"Searching in {base_path}...")
    # Find all CSV, HTML, and JSON files
    for ext in ["*.csv", "*.html", "*.json"]:
        pattern = os.path.join(base_path, "**", ext)
        # Search recursively
        try:
            for file_path in glob.glob(pattern, recursive=True):
                # Check modification time
                try:
                    mtime = os.path.getmtime(file_path)
                    dt_m = datetime.fromtimestamp(mtime)
                    # We are looking for files modified around May 18-23, 2026
                    # Since current time is May 23, 2026, let's look for anything modified in the last 10 days
                    if dt_m.year == 2026 and dt_m.month == 5 and (17 <= dt_m.day <= 23):
                        # print(f"Found recently modified file: {file_path} (Modified: {dt_m})")
                        # Read and check contents for May 19
                        try:
                            with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                                content = f.read()
                                if "2026-05-19" in content or "05/19/2026" in content or "May-19-2026" in content or "May-19" in content:
                                    print(f"!!! MATCH FOUND: {file_path} (Modified: {dt_m})")
                                    found_files.append(file_path)
                        except Exception as e:
                            pass
                except Exception as e:
                    pass
        except Exception as e:
            pass

print(f"Search complete. Found {len(found_files)} files containing May 19, 2026 trades.")
