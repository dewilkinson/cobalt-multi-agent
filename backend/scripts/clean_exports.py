import os
import sys
import glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from scripts.export_tradezella import export_tradezella

def clean_exports():
    export_dirs = [
        os.path.join(BASE_DIR, "data", "exports"),
        os.path.join(ROOT_DIR, "data", "exports")
    ]

    preserve_extensions = [".pine"]
    
    for exports_dir in export_dirs:
        if not os.path.exists(exports_dir):
            continue

        removed_count = 0
        for filename in os.listdir(exports_dir):
            path = os.path.join(exports_dir, filename)
            if not os.path.isfile(path):
                continue
                
            ext = os.path.splitext(filename)[1].lower()
            if ext in preserve_extensions:
                print(f"[PRESERVE]: {filename}")
                continue

            try:
                os.remove(path)
                removed_count += 1
                print(f"[REMOVED STALE] ({os.path.basename(exports_dir)}): {filename}")
            except Exception as e:
                print(f"[ERROR]: Failed to remove {filename}: {e}")

        print(f"[CLEANUP]: Removed {removed_count} stale files from {exports_dir}.")
    
    # Regenerate active TradeZella exports in both locations
    print("[EXPORT]: Regenerating clean TradeZella export files...")
    export_tradezella()
    print("[COMPLETE]: Both export directories clean and refreshed!")

if __name__ == "__main__":
    clean_exports()
