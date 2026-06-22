import csv
import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"
csv_paths = [
    os.path.join(workspace_dir, "data", "exports", "tradezella-import-this-week.csv"),
    os.path.join(workspace_dir, "data", "exports", "tradezella-import.csv"),
    os.path.join(workspace_dir, "backend", "data", "exports", "tradezella-import-this-week.csv")
]

def clean_csv(path):
    if not os.path.exists(path):
        print(f"File not found: {path}")
        return
        
    print(f"Cleaning CSV {path}...")
    
    rows = []
    headers = []
    
    with open(path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        headers = reader.fieldnames
        for row in reader:
            # Check if row is May 7th GLXY
            if row.get("Date") == "05/07/2026" and row.get("Symbol") == "GLXY":
                continue
            rows.append(row)
            
    # Write backup
    backup_path = path + ".bak"
    with open(backup_path, 'w', encoding='utf-8') as f:
        f.write(open(path, 'r', encoding='utf-8').read())
        
    with open(path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=headers)
        writer.writeheader()
        writer.writerows(rows)
        
    print(f"Cleaned CSV {path}. Wrote {len(rows)} rows. Backup saved to {backup_path}")

def main():
    for p in csv_paths:
        clean_csv(p)

if __name__ == "__main__":
    main()
