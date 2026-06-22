import csv
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
csv_path = os.path.join(workspace_dir, "data", "dropzone", "archive", "Activity_2026.csv")

if os.path.exists(csv_path):
    print("Found Activity_2026.csv. Rows containing GLXY:")
    with open(csv_path, 'r', encoding='utf-8') as f:
        for line in f:
            if "GLXY" in line:
                print(line.strip())
else:
    print("Activity_2026.csv not found")
