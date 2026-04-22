import json
import os
import sys
from datetime import datetime
from tradingview_screener import Query, col

def sync_vli_scanners():
    """
    Synchronizes the VLI Dashboard with real-time TradingView scanner results
    for Apex Shield and Apex Sword configurations.
    """
    print(f"[{datetime.now()}] Initiating TradingView Sync...")

    try:
        # Field list for both scanners
        # Mapping to internal names for the dashboard
        fields = [
            'name', 'close', 'change', 'relative_volume_10d_calc', 'market_cap_basic',
            'Perf.W', 'Perf.1M', 'Perf.3M', 'ATR', 'Volatility.M',
            'float_shares_outstanding', 'average_volume_30d_calc', 'Recommend.All', 'change_from_open'
        ]

        # --- 1. APEX SHIELD SCAN (Core / Institutional Leaders) ---
        shield_query = (Query()
            .set_markets('america')
            .select(*fields)
            .where(
                col('name').isin(['WELL', 'VRT', 'CDNS', 'ELV', 'FERG', 'NUE', 'STT', 'ALAB', 'STLD', 'FLEX', 'BNTX'])
            )
            .order_by('relative_volume_10d_calc', ascending=False))


        # --- 2. APEX SWORD SCAN (Satellite / High-Volatility Runners) ---
        sword_query = (Query()
            .set_markets('america')
            .select(*fields)
            .where(
                col('name').isin(['FGI'])
            )
            .order_by('relative_volume_10d_calc', ascending=False))


        # Execute Queries
        shield_df = shield_query.get_scanner_data()[1]
        sword_df = sword_query.get_scanner_data()[1]

        # Process and map for VLI Dashboard
        def map_candidate(row, tier):
            return {
                "symbol": row['name'],
                "price": row['close'],
                "change": row['change'],
                "rvol": row['relative_volume_10d_calc'],
                "market_cap": row['market_cap_basic'],
                "perf_w": row['Perf.W'],
                "perf_1m": row['Perf.1M'],
                "perf_3m": row['Perf.3M'],
                "atr": row['ATR'],
                "volatility": row['Volatility.M'],
                "tier": tier,
                "grade": "S" if row['relative_volume_10d_calc'] > 3 else "A",
                "heat_score": min(100, int(row['relative_volume_10d_calc'] * 20))
            }

        shield_candidates = [map_candidate(r, "SHIELD") for _, r in shield_df.iterrows()]
        sword_candidates = [map_candidate(r, "SWORD") for _, r in sword_df.iterrows()]

        # Final Dashboard State
        dashboard_state = {
            "pulse_mode": "TradingView (HIGH-FIDELITY)",
            "total_pulsed": len(shield_candidates) + len(sword_candidates),
            "candidates_passed": len(shield_candidates) + len(sword_candidates),
            "candidates": sword_candidates + shield_candidates,  # Swapped order to prioritize runners in main view
            "metadata": {
                "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "shield_count": len(shield_candidates),
                "sword_count": len(sword_candidates),
                "status": "active"
            }
        }

        # Persist to local data directory
        target_path = os.path.join(os.getcwd(), 'data', 'SCANNER_COMBAT_LIST.json')
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w') as f:
            json.dump(dashboard_state, f, indent=4)

        # Persist to Obsidian Vault for real-time UI rendering
        vault_path = r"c:\github\obsidian-vault\_cobalt\01_Transit\Buckets\SCANNER_RES_state.json"
        if os.path.exists(os.path.dirname(vault_path)):
            with open(vault_path, 'w') as f:
                json.dump(dashboard_state, f, indent=4)
            print(f"Vault Sync Successful: {vault_path}")

        print(f"Sync Successful: Shield({len(shield_candidates)}) | Sword({len(sword_candidates)})")

    except Exception as e:
        print(f"Sync Failed: {str(e)}")

if __name__ == "__main__":
    sync_vli_scanners()
