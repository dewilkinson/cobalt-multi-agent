import os
import sys
import shutil

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
ROOT_DIR = os.path.dirname(BASE_DIR)
sys.path.insert(0, BASE_DIR)

from scripts.export_tradezella import export_tradezella

def clean_exports():
    # Primary Single Export Directory: Workspace Root data/exports
    exports_dir = os.path.join(ROOT_DIR, "data", "exports")
    backend_exports_dir = os.path.join(BASE_DIR, "data", "exports")

    # 1. Remove redundant backend/data/exports folder if present
    if os.path.exists(backend_exports_dir):
        try:
            shutil.rmtree(backend_exports_dir)
            print(f"[REMOVED REDUNDANT DIR]: {backend_exports_dir}")
        except Exception as e:
            print(f"[WARN]: Could not remove backend/data/exports: {e}")

    # 2. Clean root data/exports directory
    if os.path.exists(exports_dir):
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

    # 3. Regenerate active TradeZella export files in single root exports directory
    print("[EXPORT]: Regenerating clean TradeZella export files...")
    export_tradezella()
    print(f"[COMPLETE]: Export directory single source of truth updated at: {exports_dir}")

if __name__ == "__main__":
    clean_exports()
