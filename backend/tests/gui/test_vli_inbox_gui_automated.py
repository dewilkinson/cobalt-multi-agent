import os
import time
import shutil
import asyncio
import requests
from playwright.async_api import async_playwright
from datetime import datetime

# --- CONFIGURATION ---
VAULT_ROOT = r"C:\github\obsidian-vault"
INBOX_PATH = os.path.join(VAULT_ROOT, "_cobalt", "inbox")
JOURNALS_PATH = os.path.join(VAULT_ROOT, "CMA journals")
ARCHIVE_PATH = os.path.join(VAULT_ROOT, "_cobalt", "archives", "action_plans")
DASHBOARD_URL = "http://127.0.0.1:8089/VLI_session_dashboard.html"
API_URL = "http://127.0.0.1:8000/api/vli"

async def run_inbox_gui_test():
    async with async_playwright() as p:
        # Launch Browser
        browser = await p.chromium.launch(headless=False, slow_mo=1000)
        recdir = os.path.abspath(os.path.join(os.path.dirname(__file__), "recordings"))
        os.makedirs(recdir, exist_ok=True)
        context = await browser.new_context(record_video_dir=recdir)
        page = await context.new_page()
        
        created_files = []
        def track_file(path):
            if path not in created_files: created_files.append(path)
            return path

        try:
            print(f"Opening Dashboard: {DASHBOARD_URL}")
            requests.post(f"{API_URL}/rule/toggle/off") # Start clean
            await page.goto(DASHBOARD_URL)
            await page.wait_for_timeout(3000)

            # --- SCENARIO 1: Synchronization Stress Test ---
            print("Scenario 1: Rapid Synchronization Test")
            batch_files = [track_file(os.path.join(INBOX_PATH, f"sync_stress_{i}.txt")) for i in range(5)]
            for fpath in batch_files:
                with open(fpath, "w") as f: f.write(f"stress test {fpath}")
            
            print("Checking for all 5 files in UI...")
            # Allow up to 10s for polling sync
            synced = False
            for _ in range(10):
                inbox_html = await page.inner_html("#inbox-pane")
                if all(os.path.basename(f) in inbox_html for f in batch_files):
                    synced = True
                    break
                await page.wait_for_timeout(1000)
            assert synced, "Not all batch files appeared in UI!"
            print("✓ Full batch sync successful.")

            # Deletion Sync
            print("Deleting 3 of 5 files...")
            to_delete = batch_files[:3]
            for f in to_delete: 
                if os.path.exists(f): os.remove(f)
            
            print("Verifying deletions in UI...")
            deleted_synced = False
            for _ in range(10):
                inbox_html = await page.inner_html("#inbox-pane")
                if all(os.path.basename(f) not in inbox_html for f in to_delete):
                    deleted_synced = True
                    break
                await page.wait_for_timeout(1000)
            assert deleted_synced, "Deleted files still visible in UI!"
            print("✓ Deletion sync successful.")

            # --- SCENARIO 2: Cooldown Verification ---
            print("Scenario 2: Archive Cooldown (10s Grace Period)")
            # The remaining 2 files should still be in the inbox (mtime is ~5s ago)
            await page.wait_for_timeout(2000)
            inbox_html = await page.inner_html("#inbox-pane")
            assert os.path.basename(batch_files[3]) in inbox_html, "File auto-archived too fast (cooldown failed)!"
            print("✓ Cooldown grace period confirmed.")

            # --- SCENARIO 3: Journal Rule ---
            print("Scenario 3: Journal Rule Filing")
            j_name = "March 30, 2026.md"
            j_path = track_file(os.path.join(INBOX_PATH, j_name))
            with open(j_path, "w") as f: f.write("# Journal")
            
            await page.click('label:has-text("RULES")')
            await page.wait_for_selector("text=2026-03-30.md", timeout=15000)
            await page.click("button:has-text('APPROVE')")
            await page.wait_for_timeout(3000)
            
            j_dest = track_file(os.path.join(JOURNALS_PATH, "2026-03-30.md"))
            assert os.path.exists(j_dest), "Journal filing failed!"
            print("✓ Journal Rule filing successful.")

            print("\nALL TEST SCENARIOS PASSED!")

        finally:
            print("\n--- STARTING CLEANUP ---")
            for f in created_files:
                if os.path.exists(f):
                    try: 
                        os.remove(f)
                        print(f"Deleted: {f}")
                    except: pass
            await browser.close()

if __name__ == "__main__":
    asyncio.run(run_inbox_gui_test())
