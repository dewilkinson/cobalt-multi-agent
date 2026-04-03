# Project Cobalt: Developer Reference Guide

This document provides deep technical specifications for the specialized subsystems of the Cobalt Multiagent (CMA) platform. Scoped for system architects and developers.

## 1. Finviz Fallback Engine

The fallback engine is triggered when `yfinance` fails to provide high-fidelity data or when indices/macro tickers are requested.

### URL Mappings
| Asset Type | Primary URL Pattern | Notes |
| :--- | :--- | :--- |
| **Futures / Indices** | `https://finviz.com/futures.ashx?t={CATEGORY}` | Categories: `INDICES`, `ENERGY`, `CURRENCIES`, etc. |
| **Stocks / ETFs** | `https://finviz.com/screener.ashx?v=152&t={TICKERS}` | Batch retrieval via comma-separated list. |

### Ticker Translation Table
The scraper uses a mandatory mapping to resolve macro symbols to their futures counterparts:
- `VIX` -> `VX`
- `DXY` / `USD` -> `DX`
- `TNX` -> `ZN`
- `TYX` -> `ZB`

## 2. Global Asset Cache Schema

Located consistently at `backend/data/playwright/heatmap_cache.json`.

```json
{
  "timestamp": 1774885603,
  "data": {
    "VX": { "price": 14.50, "source": "finviz_heatmap" }
  },
  "screenshot": "base64_encoded_string...",
  "tiles": {
    "VX": { "x": 1040.25, "y": 214.0, "w": 144.75, "h": 74.0 }
  },
  "last_target": "VIX"
}
```

### Coordinate Normalization
Coordinates are relative to the `div.grid` container on `futures.ashx`. 
- **Origin**: Top-left of the grid element.
- **Reference Resolution**: Measured against a 1280x1200 browser viewport.
- **Scaling Rule**: Frontend scaling factor = `Container_Width / 1165`.

## 3. VLI Dashboard API Reference

### GET `/api/vli/active-state`
Returns the global resonance state, including the `ux_card` directive.

**Response Schema:**
```typescript
interface UXCardDirective {
  active: boolean;      // Trigger visibility
  image: string | null; // Base64 screenshot
  target: string;       // Target ticker symbol
  highlight: {          // Normalized coordinates
    x: number;
    y: number;
    w: number;
    h: number;
  } | null;
}
```
