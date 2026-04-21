import asyncio
import os
import subprocess
import time
import sys
from playwright.async_api import async_playwright

MOCK_SERVER_SCRIPT = os.path.join(os.path.dirname(__file__), "mock_handshake_server.py")

async def update_telemetry(page, scenario, expected, result, color="yellow"):
    js_code = f"""
        const tel = document.getElementById('vli-test-telemetry');
        const log = document.getElementById('vli-telemetry-log');
        if(tel && log) {{
            tel.style.display = 'block';
            
            const entryId = 'tel-entry-{scenario}';
            let entry = document.getElementById(entryId);
            if (!entry) {{
                entry = document.createElement('div');
                entry.id = entryId;
                entry.style.display = 'flex';
                entry.style.justifyContent = 'space-between';
                entry.style.borderBottom = '1px solid rgba(255,255,255,0.1)';
                entry.style.paddingBottom = '8px';
                log.appendChild(entry);
            }}
            
            entry.innerHTML = `
                <span style="color: white; width: 250px;">[{scenario.upper()}]</span>
                <span style="color: #8b949e; flex: 1;">Expected: {expected}</span>
                <span style="color: {color}; font-weight: bold; width: 100px; text-align: right;">{result}</span>
            `;
            
            tel.scrollTop = tel.scrollHeight;
        }}
    """
    try:
        await page.evaluate(js_code)
    except:
        pass

async def run_test_case(page, scenario: str, expected_title: str, expected_reason: str, timeout: int):
    print(f"[{scenario.upper()}] Starting Test Case...")
    
    env = os.environ.copy()
    env["MOCK_SCENARIO"] = scenario
    
    server_process = None
    
    if scenario == "timeout":
        print(f"[{scenario.upper()}] Server intentionally NOT started to simulate hard offline.")
        # Ensure nothing is on 8000
        subprocess.run('FOR /F "tokens=5" %P IN (\'netstat -a -n -o ^| findstr :8000\') DO TaskKill.exe /PID %P /F', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
    else:
        # forcefully kill port 8000 just in case
        subprocess.run('FOR /F "tokens=5" %P IN (\'netstat -a -n -o ^| findstr :8000\') DO TaskKill.exe /PID %P /F', shell=True, stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        
        server_process = subprocess.Popen(
            [sys.executable, MOCK_SERVER_SCRIPT], 
            env=env,
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL
        )
        time.sleep(2)  # Wait for uvicorn to boot
        print(f"[{scenario.upper()}] Mock server running.")

    result = "FAIL"
    
    try:
        # Trigger handshake sequence manually since the page is already loaded
        await page.evaluate("if(window.vliStartHandshake) window.vliStartHandshake();")
        
        await update_telemetry(page, scenario, expected_title, "RUNNING...", "yellow")
        
        print(f"[{scenario.upper()}] Waiting for handshake resolution (up to {timeout}s)...")
        
        start_wait = time.time()
        found = False
        
        while time.time() - start_wait < timeout:
            await update_telemetry(page, scenario, expected_title, "RUNNING...", "yellow")
            
            title_elem = await page.query_selector("#vli-handshake-title")
            if title_elem:
                title_text = await title_elem.inner_text()
                
                if expected_title.lower() in title_text.lower():
                    found = True
                    break
                        
            await asyncio.sleep(0.5)
            
        if found:
            result = "PASS"
            color = "#3fb950"
            print(f"[{scenario.upper()}] SUCCESS: Reached expected state '{expected_title}'")
            
            if scenario == "mismatch_restart":
                print(f"[{scenario.upper()}] Waiting for MANUAL retry to verify recovery (You have 30s)...")
                await update_telemetry(page, scenario, "Waiting for MANUAL Retry...", "RETRYING...", "yellow")
                
                start_retry = time.time()
                found_retry = False
                while time.time() - start_retry < 30:
                    t_elem = await page.query_selector("#vli-handshake-title")
                    if t_elem and "Connected!" in await t_elem.inner_text():
                        found_retry = True
                        break
                    await asyncio.sleep(0.5)
                
                if found_retry:
                    print(f"[{scenario.upper()}] RETRY SUCCESS: Connected!")
                    expected_title = "Retry -> Connected!"
                else:
                    print(f"[{scenario.upper()}] RETRY FAILED.")
                    result = "FAIL"
                    color = "#f85149"
        else:
            color = "#f85149"
            print(f"[{scenario.upper()}] FAILED.")
            
        await update_telemetry(page, scenario, expected_title, result, color)
        
        # Hold to let user verify messages
        await asyncio.sleep(3)
        
    except Exception as e:
        print(f"[{scenario.upper()}] ERROR: {e}")
        time.sleep(2)
    finally:
        if server_process:
            server_process.terminate()
            server_process.wait()
            
    print(f"[{scenario.upper()}] RESULT: {result}\n")
    return result == "PASS"

async def main():
    print("==========================================")
    print("  VLI CLIENT-SERVER HANDSHAKE TEST SUITE  ")
    print("==========================================\n")
    
    tests = [
        ("success", "Connected!", None, 10),
        ("delayed_start", "Connected!", None, 20),
        ("mismatch_restart", "FAILED: VERSION MISMATCH", None, 15),
        ("timeout", "FAILED: TIMEOUT", None, 20)
    ]
    
    # We must load the page initially. We will boot a dummy server to serve the page.
    env = os.environ.copy()
    env["MOCK_SCENARIO"] = "success"
    init_server = subprocess.Popen(
        [sys.executable, MOCK_SERVER_SCRIPT], 
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL
    )
    time.sleep(2)
    
    passed = 0
    
    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=False)
        page = await browser.new_page()
        
        url = "http://127.0.0.1:8000/VLI_session_dashboard.html"
        print(f"[INIT] Navigating to {url} ...")
        await page.goto(url)
        
        # We kill the init server, because the actual tests will spin up their own servers
        init_server.terminate()
        init_server.wait()
        
        # Give page a second to stabilize after init
        await asyncio.sleep(2)
        await page.evaluate("const tel = document.getElementById('vli-test-telemetry'); if(tel) tel.style.display = 'block';")
        
        for scenario, exp_title, exp_reason, to in tests:
            res = await run_test_case(page, scenario, exp_title, exp_reason, to)
            if res:
                passed += 1
                
        # Final hold before closing the entire session
        await update_telemetry(page, "ALL DONE", f"{passed}/{len(tests)} PASSED", "FINISHED", "#58a6ff")
        await asyncio.sleep(10)
        
        await browser.close()
            
    print("==========================================")
    print(f"  SUITE COMPLETE: {passed}/{len(tests)} PASSED")
    print("==========================================")

if __name__ == "__main__":
    asyncio.run(main())
