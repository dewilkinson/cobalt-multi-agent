import os
import sys
import glob

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, BASE_DIR)

from scripts.export_tradezella import export_tradezella

def clean_exports():
    exports_dir = os.path.join(BASE_DIR, "data", "exports")
    if not os.path.exists(exports_dir):
        print("[INFO]: Exports directory does not exist.")
        return

    # Keep list of essential non-trade export files (e.g. Pine scripts)
    preserve_extensions = [".pine"]
    
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
            print(f"[REMOVED STALE]: {filename}")
        except Exception as e:
            print(f"[ERROR]: Failed to remove {filename}: {e}")

    print(f"[CLEANUP]: Removed {removed_count} stale files from {exports_dir}.")
    
    # Regenerate active TradeZella exports
    print("[EXPORT]: Regenerating clean TradeZella export files...")
    export_tradezella()
    print("[COMPLETE]: Export directory clean and refreshed!")

if __name__ == "__main__":
    clean_exports()
