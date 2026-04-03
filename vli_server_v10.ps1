# VLI Command Center V10 - Institutional Launcher
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>

Write-Host "🚀 Launching VLI Command Center V10 (Decoupled Infrastructure)..." -ForegroundColor Cyan

# 1. Start the Macro Worker in a background process
Write-Host "1. Initializing Institutional Macro Worker..." -ForegroundColor Yellow
Start-Process python -ArgumentList "backend/scripts/vli_macro_worker.py" -NoNewWindow

# 2. Start the API Server
Write-Host "2. Starting VLI API Server on http://localhost:8000..." -ForegroundColor Green
python backend/server.py --port 8000
