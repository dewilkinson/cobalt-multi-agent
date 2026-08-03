import csv
import os
import glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def find_raw_topstep_file():
    archive_dir = os.path.join(BASE_DIR, "data", "dropzone", "archive")
    matches = glob.glob(os.path.join(archive_dir, "*topstep*.csv"))
    if matches:
        return max(matches, key=os.path.getctime)
    return os.path.join(BASE_DIR, "data", "exports", "tradezella-import-TopStepX.csv")

def generate_native_topstep_export():
    raw_path = find_raw_topstep_file()
    print(f"Reading raw TopStep file: {raw_path}")

    with open(raw_path, 'r', encoding='utf-8') as f:
        rows = list(csv.DictReader(f))

    if not rows:
        print("No rows found.")
        return

    fieldnames = list(rows[0].keys())

    clean_rows = []
    for r in rows:
        r_copy = dict(r)
        
        # Clean EnteredAt & ExitedAt (remove timezone offset string)
        if 'EnteredAt' in r_copy:
            r_copy['EnteredAt'] = r_copy['EnteredAt'].split(' -')[0].split(' +')[0].strip()
        if 'ExitedAt' in r_copy:
            r_copy['ExitedAt'] = r_copy['ExitedAt'].split(' -')[0].split(' +')[0].strip()
            
        # Clean TradeDay to simple date MM/DD/YYYY
        if 'TradeDay' in r_copy:
            td_clean = r_copy['TradeDay'].split(' -')[0].split(' +')[0].strip()
            r_copy['TradeDay'] = td_clean.split(' ')[0]

        clean_rows.append(r_copy)

    target_path = os.path.join(BASE_DIR, "data", "exports", "tradezella-import-TopStepX.csv")
    with open(target_path, 'w', newline='', encoding='utf-8') as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(clean_rows)

    print(f"[SUCCESS] Native TopStepX CSV with clean dates written to -> {target_path}")

if __name__ == "__main__":
    generate_native_topstep_export()
