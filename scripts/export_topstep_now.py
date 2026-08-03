import os
import glob
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

def export_raw_topstep():
    archive_dir = os.path.join(BASE_DIR, "data", "dropzone", "archive")
    matches = glob.glob(os.path.join(archive_dir, "*topstep*.csv"))
    if not matches:
        print("No TopStep files found.")
        return

    # Sort strictly by last modified time to pick the newest raw download
    matches.sort(key=os.path.getmtime, reverse=True)
    latest_file = matches[0]

    target_file = os.path.join(BASE_DIR, "data", "exports", "tradezella-import-TopStepX.csv")
    os.makedirs(os.path.dirname(target_file), exist_ok=True)

    # Direct raw byte copy - untouched
    shutil.copy2(latest_file, target_file)

    print(f"[SUCCESS] Exported raw untouched TopStep CSV from {latest_file} -> {target_file}")

if __name__ == "__main__":
    export_raw_topstep()
