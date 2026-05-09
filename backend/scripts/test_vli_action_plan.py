import os
import time
from datetime import datetime

import requests

# --- CONFIGURATION ---
VAULT_ROOT = r"C:\github\obsidian-vault"
COBALT_DIR = "_cobalt"
INBOX_DIR = "inbox"
ARCHIVE_DIR = "archives"
ACTION_PLAN_DIR = "action_plans"

# Derived paths
inbox_path = os.path.join(VAULT_ROOT, COBALT_DIR, INBOX_DIR)
archive_path = os.path.join(VAULT_ROOT, COBALT_DIR, ARCHIVE_DIR)
plan_dir = os.path.join(VAULT_ROOT, COBALT_DIR, ACTION_PLAN_DIR)
today = datetime.now().strftime("%Y-%m-%d")
active_plan_file = os.path.join(plan_dir, f"{today} Action Plan.md")

# Sample content from historical plans
BUNKER_PLAN = """### **Bunker Mode Design: Time-Horizon Selection**

To advance the design discussion, we must address the **Structural Hierarchy** during a Bunker regime.
When the $20–$50 and RVOL requirements are relaxed, we are often dealing with "Shields" 
that possess significantly deeper liquidity pools (e.g., $XLE, $ITA, or Mega-caps like $WM).

**Sortino-Relative Strength (SRS) Integration:**
In the DeerFlow 2.0 design, the **Analyst Agent** will run a "Sweep" of the 1-Hour charts *only* 
for symbols that have cleared the Daily/4-Hour Sortino hurdle ($S_{DR} >= 2.0$).

Please create me a new watchlist window for Futures to monitor these shields.
"""


def run_functional_test():
    print("---  STARTING VLI FUNCTIONAL TEST ---")

    # 1. Cleanup & Preparation
    os.makedirs(inbox_path, exist_ok=True)
    os.makedirs(archive_path, exist_ok=True)
    os.makedirs(plan_dir, exist_ok=True)

    test_file = os.path.join(inbox_path, "bunker_mode_test.md")
    print(f"1. Creating sample action plan in inbox: {test_file}")
    with open(test_file, "w", encoding="utf-8") as f:
        f.write(BUNKER_PLAN)

    # 2. Waiting for Reactive Monitor
    print("2. Waiting for VLI watcher (0.5s polling)...")
    max_wait = 10
    start_time = time.time()
    found = False

    while time.time() - start_time < max_wait:
        if not os.path.exists(test_file):
            print("    Inbox file captured!")
            found = True
            break
        time.sleep(0.5)

    if not found:
        print("    TIMEOUT: Watcher did not capture the file.")
        return

    # 3. Verify Active State via API
    print("3. Verifying dashboard state (symbols/logic extraction)...")
    try:
        resp = requests.get("http://localhost:8000/api/vli/active-state", timeout=5)
        data = resp.json()

        alerts = data.get("alerts", [])
        symbols = [a["symbol"] for a in alerts]
        labels = [a["label"] for a in alerts]

        # Check for $XLE, $ITA, $WM and S_{DR} >= 2.0
        expected_syms = ["XLE", "ITA", "WM", "LOGIC"]
        missing = [s for s in expected_syms if s not in symbols]

        if not missing:
            print(f"    SUCCESS: All symbols extracted: {symbols}")
        else:
            print(f"    WARNING: Missing symbols from extraction: {missing}")

        # 4. Verify Dynamic Panels
        print("4. Verifying dynamic panel creation (Futures Watchlist)...")
        panels = data.get("dynamic_panels", [])
        if any(p["id"] == "watch-futures-01" for p in panels):
            print("    SUCCESS: Futures Watchlist dynamic panel found in state.")
        else:
            print("    FAIL: Futures Watchlist dynamic panel NOT found.")

    except Exception as e:
        print(f"    API verification failed (is server running?): {e}")

    # 5. Verify Archive
    print("5. Verifying archive protocol...")
    archived_files = os.listdir(archive_path)
    if any("bunker_mode_test" in f for f in archived_files):
        print("    SUCCESS: File moved to archives.")
    else:
        print("    FAIL: File not found in archives.")

    print("\n---  TEST COMPLETE ---")


if __name__ == "__main__":
    run_functional_test()
