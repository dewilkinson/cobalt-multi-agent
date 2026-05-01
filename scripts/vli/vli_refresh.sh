#!/bin/bash

# VLI DASHBOARD REFRESH & CLEANUP
# This script forcefully terminates stale VLI processes and restarts the dashboard.

echo "--------------------------------------------------"
echo "🚀 VLI DASHBOARD: EMERGENCY CLEANUP & RESTART"
echo "--------------------------------------------------"

# 1. KILL STALE PROCESSES
echo "[1/4] Terminating existing VLI processes on port 8000..."
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    # Windows (Git Bash / MSYS)
    PORT_PID=$(netstat -ano | grep :8000 | grep LISTENING | awk '{print $5}' | head -n 1)
    if [ ! -z "$PORT_PID" ]; then
        taskkill -F -PID $PORT_PID
        echo "      ✔ Killed Windows process $PORT_PID"
    fi
else
    # Linux / macOS
    fuser -k 8000/tcp 2>/dev/null
    echo "      ✔ Ports cleared."
fi

# 2. STATE PURGE
echo "[2/4] Purging stale session state..."
rm -f active_state.json active_state_debug.json
rm -f backend/vli_test.db
echo "      ✔ State files cleared."

# 3. LAUNCH BACKEND
echo "[3/4] Launching VLI Backend..."
cd backend
# We use nohup or & to run in background so we can launch the browser
uv run server.py > ../vli_server.log 2>&1 &
SERVER_PID=$!
echo "      ✔ Backend started (PID: $SERVER_PID). Logs: vli_server.log"

# 4. LAUNCH DASHBOARD
echo "[4/4] Launching VLI Dashboard in browser..."
sleep 2 # Wait for uvicorn to bind
if [[ "$OSTYPE" == "msys" || "$OSTYPE" == "win32" ]]; then
    start http://localhost:8000/vli_dashboard.html
else
    # Linux/macOS
    open http://localhost:8000/vli_dashboard.html 2>/dev/null || xdg-open http://localhost:8000/vli_dashboard.html 2>/dev/null
fi

echo "--------------------------------------------------"
echo "✅ VLI System Restored."
echo "Keep this terminal open to maintain the backend."
echo "--------------------------------------------------"

# Bring backend to foreground so user can see logs and use Ctrl+C
wait $SERVER_PID
