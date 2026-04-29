import argparse
import asyncio
import time
import os
from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
import uvicorn
from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

SCENARIO = os.environ.get("MOCK_SCENARIO", "success")
START_TIME = time.time()
RESTART_TIME = None

# Using the version we just generated
CLIENT_VERSION = "00.000.0004"

@app.get("/vli_dashboard.html")
async def get_dashboard():
    # Serve the actual dashboard file
    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "public", "vli_dashboard.html"))
    return FileResponse(file_path)

@app.get("/sw.js")
async def get_sw():
    # Serve the service worker file
    file_path = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", "public", "sw.js"))
    return FileResponse(file_path, media_type="application/javascript")

@app.get("/api/health")
async def health():
    elapsed = time.time() - START_TIME
    
    if SCENARIO == "success":
        # Simulate realistic 0.5s connection latency
        await asyncio.sleep(0.5)
        return {"status": "ok", "version": CLIENT_VERSION}
        
    elif SCENARIO == "delayed_start":
        if elapsed < 8.0:
            # Simulate server offline for 8 seconds
            raise HTTPException(status_code=502)
        return {"status": "ok", "version": CLIENT_VERSION}
        
    elif SCENARIO == "mismatch_restart":
        global RESTART_TIME
        if RESTART_TIME is not None:
            # Server is in 'restarting' phase
            restart_elapsed = time.time() - RESTART_TIME
            if restart_elapsed < 8.0:
                # Simulate offline while rebooting for 8 seconds
                raise HTTPException(status_code=502)
            # Reboot complete, version now matches
            return {"status": "ok", "version": CLIENT_VERSION}
            
        # Initial connection: version mismatch
        return {"status": "ok", "version": "00.000.0000"}
        
    elif SCENARIO == "timeout":
        # Always offline (simulating 30s timeout)
        raise HTTPException(status_code=502)

@app.post("/api/system/restart")
async def restart():
    if SCENARIO == "mismatch_restart":
        global RESTART_TIME
        RESTART_TIME = time.time()
        return {"status": "restarting"}
    return {"status": "ok"}

@app.get("/api/vli/active-state")
async def active_state():
    return {
        "status": "active",
        "current_agent": "system",
        "system_status": "ONLINE",
        "macro_status": "Tracking",
        "shield_status": "Active",
        "swords_status": "Active"
    }

@app.get("/api/scanner/state")
async def scanner_state():
    return {"status": "idle", "last_scan": "Just now", "results": []}

@app.get("/api/scanner/shield-bunker")
async def shield_bunker():
    return []

if __name__ == "__main__":
    print(f"==========================================")
    print(f"  RUNNING MOCK HANDSHAKE SERVER")
    print(f"  SCENARIO: {SCENARIO}")
    print(f"==========================================")
    uvicorn.run(app, host="127.0.0.1", port=8000)
