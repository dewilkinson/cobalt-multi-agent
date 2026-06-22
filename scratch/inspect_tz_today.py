import csv
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
csv_path = os.path.join(workspace_dir, "data", "exports", "tradezella-import.csv")

if os.path.exists(csv_path):
    print("Found tradezella-import.csv. All rows:")
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            print(row)
else:
    print("CSV not found")
