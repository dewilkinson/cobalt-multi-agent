# Automated Background Analysis & UI Integration (Updated)

We will build an automated pipeline that ensures deep-dive LLM reports are pre-generated for scanner targets without spamming the live chat terminal, and surface those reports seamlessly in the dashboard.

## Proposed Changes

### 1. Backend: Background Analysis Orchestrator
- **File**: `backend/src/server/app.py`
  - [MODIFY] Add a new APScheduler cron job (`run_daily_morning_analysis`) scheduled for 6:00 AM EDT.
  - [MODIFY] Add an "idle checker" task (`run_idle_analysis`) that runs periodically. It will diff the current scanner list against the `data/reports/` directory.
  - **[UPDATED] Rate Limiting**: The background runner will process missing symbols sequentially with a **30-second `asyncio.sleep` stagger** to strictly protect the Gemini Ultra Tier's TPM and RPM limits.
  - **[NEW] Midnight Cache Invalidation**: The script will check the creation/modification timestamp of the existing `analyze_{symbol}.md` files. If a file exists but was generated *before midnight* of the current day, it will be considered stale and automatically flagged for regeneration.

### 2. Backend: New Administrative Commands
- **File**: `backend/src/tools/scanner.py`
  - [NEW] Add `@tool async def trigger_manual_analysis_scan() -> str`: A tool that the user can manually invoke via chat (e.g., `"run missing analysis scans"`) to instantly trigger the background checker without waiting for the idle loop.
  - [NEW] Add `@tool async def evict_analysis_report(ticker: str) -> str`: A tool that allows the user to manually delete a cached report via chat (e.g., `"evict report for AAPL"` or `"clear AAPL cache"`).

### 3. Backend: Report State Injection & Endpoint
- **File**: `backend/scripts/tv_scanner_sync.py`
  - [MODIFY] During the mapping phase, the script will check if `data/reports/analyze_{symbol.lower()}.md` exists and was created *today*. It will append `has_report: true/false` to the JSON payload.
- **File**: `backend/src/server/app.py`
  - [MODIFY] Add a new REST endpoint: `GET /api/vli/report/{symbol}` which reads the requested markdown file from disk and serves it.

### 4. Frontend: Document Icon & Modal UI
- **File**: `backend/public/VLI_session_dashboard.html`
  - [MODIFY] In `renderScannerResults` and `renderShieldResults`, inject a document icon (`<i class="fas fa-file-alt"></i>`) next to the Grade badge.
  - If `c.has_report === true`, the icon will be green (`var(--emerald-green)`). If false, it will be gray.
  - [NEW] Add a hidden modal overlay (`#report-modal`) and an `openReportModal(symbol)` function triggered by clicking the icon. It will hit the new backend endpoint, parse the Markdown, and display the report cleanly.

## User Review Required

The plan has been fully updated to incorporate the Gemini Ultra rate-limiting safeguards, the manual trigger/eviction commands, and the midnight cache invalidation logic. 

If this looks good, please approve and I will begin execution!
