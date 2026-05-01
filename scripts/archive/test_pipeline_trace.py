import asyncio
import httpx
import time
import os
import json
import logging
import sys

logging.basicConfig(level=logging.INFO)

# Force stdout to utf-8 for emojis
sys.stdout.reconfigure(encoding='utf-8')

async def run_trace():
    print("=== STARTING DIAGNOSTIC TRACE ===")
    
    # 1. Simulate "run morning scan"
    print("\n1. Triggering /api/vli/action-plan with 'RUN MORNING SCAN'...")
    async with httpx.AsyncClient() as client:
        resp = await client.post("http://127.0.0.1:8000/api/vli/action-plan", json={
            "text": "RUN MORNING SCAN",
            "direct_mode": True,
            "raw_data_mode": False,
            "background_synthesis": True,
            "thread_id": "test-trace"
        }, timeout=10.0)
        print(f"Response Status: {resp.status_code}")
        print(f"Response Body: {resp.json()}")

    # 2. Check the raw file
    print("\n2. Checking VLI_Raw_Telemetry.md...")
    time.sleep(2)  # Give bg_task time to write
    telemetry_path = r"c:\github\obsidian-vault\_cobalt\VLI_Raw_Telemetry.md"
    if os.path.exists(telemetry_path):
        with open(telemetry_path, "r", encoding="utf-8") as f:
            lines = f.readlines()
            print("Last 10 lines of telemetry file:")
            for line in lines[-10:]:
                print(line.strip())
                
    # 3. Simulate the UI polling
    print("\n3. Simulating UI polling GET /api/vli/active-state...")
    async with httpx.AsyncClient() as client:
        resp = await client.get(f"http://127.0.0.1:8000/api/vli/active-state?t={int(time.time()*1000)}", timeout=10.0)
        data = resp.json()
        tail = data.get("telemetry_tail", "")
        print(f"Telemetry Tail returned (last 500 chars):")
        print(tail[-500:])

if __name__ == "__main__":
    asyncio.run(run_trace())
