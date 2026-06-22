# VLI DASHBOARD REFRESH & CLEANUP (PowerShell)
# This script forcefully terminates stale VLI processes and restarts the dashboard.

Write-Host "--------------------------------------------------" -ForegroundColor Cyan
Write-Host "VLI DASHBOARD: EMERGENCY CLEANUP & RESTART" -ForegroundColor Cyan
Write-Host "--------------------------------------------------" -ForegroundColor Cyan

# 1. KILL STALE PROCESSES
Write-Host "[1/4] Terminating existing VLI processes on port 8000..."
try {
    $connections = Get-NetTCPConnection -LocalPort 8000 -ErrorAction SilentlyContinue
    if ($connections) {
        $portProc = $connections | Select-Object -ExpandProperty OwningProcess -Unique
        foreach ($p in $portProc) {
            Stop-Process -Id $p -Force -ErrorAction SilentlyContinue
            Write-Host "      Killed process $p"
        }
    } else {
        Write-Host "      Port 8000 is already clear."
    }
} catch {
    Write-Host "      Error clearing port 8000: $($_.Exception.Message)"
}

# 2. STATE PURGE
Write-Host "[2/4] Purging stale session state..."
$filesToPurge = @(
    "active_state.json", 
    "active_state_debug.json", 
    "backend/vli_test.db",
    "backend/data/vli_macro_snapshot.json",
    "data/vli_macro_snapshot.json"
)
foreach ($f in $filesToPurge) {
    if (Test-Path $f) {
        Remove-Item -Path $f -Force -ErrorAction SilentlyContinue
        Write-Host "      Cleared: $f"
    }
}

# [NEW] Backup current BrokerageCache before clearing (optional safety)
$cacheFile = "data/brokerage_cache.json"
if (Test-Path $cacheFile) {
    $backupPath = "data/archive/brokerage_cache_pre_refresh.json"
    New-Item -ItemType Directory -Path "data/archive" -Force | Out-Null
    Copy-Item -Path $cacheFile -Destination $backupPath -Force
    Write-Host "      Backed up brokerage cache to: $backupPath"
}

# 3. LAUNCH BACKEND
Write-Host "[3/4] Launching VLI Backend..."
if (Test-Path "backend") {
    Push-Location "backend"
    # [HARDENING] Check for uv vs python
    $cmd = "python"
    if (Get-Command "uv" -ErrorAction SilentlyContinue) {
        $cmd = "uv"
        $args = @("run", "server.py")
    } else {
        $args = @("server.py")
    }
    Write-Host "      (Using $cmd to launch backend)"
    Start-Process -FilePath $cmd -ArgumentList $args -NoNewWindow
    Pop-Location
    Write-Host "      Backend started."
} else {
    Write-Host "      Backend directory not found!"
}

# 4. LAUNCH DASHBOARD
Write-Host "[4/4] Backend ready. (Dashboard should be launched via start-desktop.bat)"
Start-Sleep -Seconds 3
# Start-Process "http://localhost:8000/vli_dashboard.html"

Write-Host "--------------------------------------------------" -ForegroundColor Green
Write-Host "VLI System Restored." -ForegroundColor Green
Write-Host "--------------------------------------------------" -ForegroundColor Green
