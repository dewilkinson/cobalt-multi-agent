# Upgrade Fidelity Bridge Extension

Currently, the `Fidelity Bridge VLI` extension is strictly designed to scrape the Orders/Activity page for high-fidelity intraday execution timestamps (since Fidelity's CSV exports default to 00:00:00). It does not currently scrape active positions, nor does it issue notifications.

To fulfill your request, I propose the following upgrades to both the Extension and the Backend.

## User Review Required

> [!WARNING]
> Since the extension relies on DOM scraping, any changes to Fidelity's UI could break this logic. We will target standard data-grid attributes to ensure maximum resilience.

## Proposed Changes

### 1. Extension Position Scraping (content.js)
- Extend the `content.js` script to detect when the user is on the `Positions` tab (e.g. looking for `.pos-symbol` or `.pos-quantity` classes).
- If on the Positions tab, scrape the active symbols, quantities, and cost basis.
- Send this payload to `/api/fidelity/sync` with `payloadType: 'positions'`.

### 2. Backend Position Ingestion (brokerage_cache.py)
- Update `BrokerageCache.ingest_fidelity_payload` to handle `payloadType: 'positions'`.
- Override the `positions` list in `brokerage_cache.json` with the newly scraped live data, ensuring it remains synchronized in real-time.

### 3. Real-Time Trade Notifications (brokerage_cache.py)
- Modify the existing execution time ingestion logic in `ingest_fidelity_payload`.
- When a new trade timestamp is discovered that *did not previously exist* in the cache, trigger a system-wide notification.
- We can route this notification via the `logger`, or inject it into the `CobaltScheduler` UI stream so it pops up directly on your VLI dashboard.

## Verification Plan

### Manual Verification
1. I will write a mock DOM payload containing a new trade and send it to the backend via a manual `POST` request to test if the notification triggers.
2. I will send a mock DOM payload containing position data to verify that the cache updates and correctly propagates to the frontend.
3. You will need to reload the Chrome extension (`chrome://extensions`) and open your Fidelity positions page to verify end-to-end functionality in your live environment.
