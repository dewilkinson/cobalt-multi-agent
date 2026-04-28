# Color-Coded Macro Thresholds

We need to add a visual, color-coded semitransparent background to the key macro indices in the Macro Watchlist to quickly convey market risk states.

## Open Questions

> [!IMPORTANT]
> **Threshold Values Confirmation:** I have inferred the key indices you use for entries/exits are **Yields (^TNX)** and **Volatility (^VIX)**. I am proposing the following thresholds based on standard risk metrics and our previous context (.TNX > 4.30%). Please confirm or adjust these values before I proceed.

### Proposed ^TNX (10-Year Yield) Thresholds:
- **Red (High Risk):** >= 4.50%
- **Orange (Elevated):** >= 4.30%
- **Yellow (Moderate):** >= 4.00%
- **Green (Favorable):** < 4.00%

### Proposed ^VIX (Volatility) Thresholds:
- **Red (High Risk):** >= 25.0
- **Orange (Elevated):** >= 20.0
- **Yellow (Moderate):** >= 15.0
- **Green (Favorable):** < 15.0

*Are there any other key indices (e.g., DXY) you want threshold backgrounds applied to? If so, please provide their thresholds.*

## Proposed Changes

### `backend/public/VLI_session_dashboard.html`
- **[MODIFY]** `renderWatchlist(data)` function.
- Introduce a helper function `getMacroRowBackground(ticker, value)` that applies the threshold logic and returns a semitransparent background color (`rgba`).
- Apply this background color to the `tr.style.background` for the corresponding rows in the Macro Watchlist.

## Verification Plan

### Manual Verification
- Once implemented, the UI will immediately reflect the background colors based on the current live values of ^TNX and ^VIX.
- I will verify the code syntax and ensure it integrates cleanly with the existing row highlighting logic in the dashboard.
