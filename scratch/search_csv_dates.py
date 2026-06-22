import csv
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
csv_path = os.path.join(workspace_dir, "data", "exports", "tradezella-import-this-week.csv")

if os.path.exists(csv_path):
    dates = set()
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            dates.add((row.get("Date"), row.get("Symbol")))
    print("All Date-Symbol pairs in tradezella-import-this-week.csv:")
    for d, s in sorted(dates):
        print(f"Date: {d} | Symbol: {s}")
else:
    print("CSV not found")
