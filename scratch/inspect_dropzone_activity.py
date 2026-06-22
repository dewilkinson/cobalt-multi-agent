import os
import csv

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
dropzone_dir = os.path.join(workspace_dir, "data", "dropzone")

# List files in dropzone
print("Files in dropzone:")
for root, dirs, files in os.walk(dropzone_dir):
    for f in files:
        print(os.path.join(root, f))

# Let's inspect Activity_2026.csv if it exists
csv_path = os.path.join(dropzone_dir, "Activity_2026.csv")
if not os.path.exists(csv_path):
    csv_path = os.path.join(dropzone_dir, "archive", "Activity_All_Accounts.csv")

if os.path.exists(csv_path):
    print(f"\nInspecting {csv_path} for GLXY:")
    with open(csv_path, 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    header_idx = -1
    for i, line in enumerate(lines):
        if "Symbol" in line and "Description" in line:
            header_idx = i
            break
    if header_idx != -1:
        reader = csv.DictReader(lines[header_idx:])
        count = 0
        for row in reader:
            if "GLXY" in str(row.values()):
                print(row)
                count += 1
                if count > 20:
                    break
else:
    print(f"\n{csv_path} not found")
