import json
import os
import sys
import asyncio
from datetime import datetime
from tradingview_screener import Query, col

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))
from src.tools.scanner import batch_fetch_sortino

def sync_vli_scanners():
    """
    Synchronizes the VLI Dashboard with real-time TradingView scanner results
    for Apex Shield and Apex Sword configurations.
    """
    print(f"[{datetime.now()}] Initiating TradingView Sync...")

    # [MINIMIZED] Immediate Telemetry for Start Sequence suppressed in favor of summary
    pass

    try:
        # Field list for both scanners
        # Mapping to internal names for the dashboard
        fields = [
            'name', 'close', 'change', 'relative_volume_10d_calc', 'market_cap_basic',
            'Perf.W', 'Perf.1M', 'Perf.3M', 'ATR', 'Volatility.M', 'volume', 'SMA200', 'SMA50',
            'float_shares_outstanding', 'average_volume_30d_calc', 'Recommend.All', 'change_from_open'
        ]

        # --- 1. APEX SHIELD SCAN (Core / Institutional Leaders) ---
        shield_query = (Query()
            .set_markets('america')
            .select(*fields)
            .where(
                col('exchange').isin(['NASDAQ', 'NYSE']),
                col('close') > 15,
                col('change').between(3, 8),
                col('market_cap_basic') > 300_000_000,
                col('volume') > 1_000_000,
                col('float_shares_outstanding') > 100_000_000,
                col('ATR') > 1,
                col('close') > col('SMA200'),
                col('Volatility.M') > 2
            )
            .order_by('relative_volume_10d_calc', ascending=False)
            .limit(25))

        # --- 2. APEX SWORD SCAN (Satellite / High-Volatility Runners) ---
        sword_query = (Query()
            .set_markets('america')
            .select(*fields)
            .where(
                col('exchange').isin(['NASDAQ', 'NYSE']),
                col('type') == 'stock',
                col('subtype') == 'common',
                col('close').between(1, 20),
                col('market_cap_basic').between(100_000_000, 2_000_000_000),
                col('volume') > 500_000,
                col('float_shares_outstanding') < 100_000_000,
                col('ATR') > 0.75,
                col('close') > col('SMA50'),
                col('Volatility.M') > 5,
                col('relative_volume_10d_calc') > 2,
                col('change') > 3,
                col('Recommend.All') >= 0.1
            )
            .order_by('relative_volume_10d_calc', ascending=False)
            .limit(20))


        # Execute Queries
        shield_df = shield_query.get_scanner_data()[1]
        sword_df = sword_query.get_scanner_data()[1]

        raw_all = shield_df['name'].tolist() + sword_df['name'].tolist()
        
        # [MINIMIZED] Telemetry for query completion suppressed
        pass

        removed_trace = []

        # Process and map for VLI Dashboard
        def map_candidate(row, tier):
            symbol = row['name']
            
            # [HARDENING] Strict sanitization
            if any(char in symbol for char in ['.', '-', '/', '^', '=']):
                removed_trace.append(f"   ❌ Removed: **{symbol}** (Invalid Characters)")
                return None
            if len(symbol) > 4 and symbol[-1] in ['W', 'U', 'R', 'P']:
                removed_trace.append(f"   ❌ Removed: **{symbol}** (Preferred/Warrant Filter)")
                return None
                
            return row

        clean_shield = [r for r in (map_candidate(r, "SHIELD") for _, r in shield_df.iterrows()) if r is not None]
        clean_sword = [r for r in (map_candidate(r, "SWORD") for _, r in sword_df.iterrows()) if r is not None]

        # [MINIMIZED] Sanitization Trace suppressed
        pass

        # Fetch Sortino for surviving candidates
        all_symbols = [r['name'] for r in clean_shield] + [r['name'] for r in clean_sword]
        
        # [MINIMIZED] Sortino calculation telemetry suppressed
        pass
            
        print(f"Fetching localized Sortino ratios for {len(all_symbols)} candidates...")
        sortino_map = asyncio.run(batch_fetch_sortino(all_symbols, period="20d"))

        def finalize_candidate(row, tier, sortino_map):
            symbol = row['name']
            report_path = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{symbol.lower()}.md')
            
            # [HARDENING] Strict sanitization to prevent preferred/warrants/units and hallucinated strings
            if any(char in symbol for char in ['.', '-', '/', '^', '=']):
                removed_trace.append(f"   ❌ Removed: **{symbol}** (Invalid Characters)")
                return None
            if len(symbol) > 4 and symbol[-1] in ['W', 'U', 'R', 'P']:
                removed_trace.append(f"   ❌ Removed: **{symbol}** (Preferred/Warrant Filter)")
                return None
                
            report_path = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{symbol.lower()}.md')
            updated_at = None
            has_report = False
            if os.path.exists(report_path):
                mtime = datetime.fromtimestamp(os.path.getmtime(report_path))
                updated_at = mtime.isoformat()
                if mtime.date() == datetime.now().date():
                    has_report = True
                    
            return {
                "symbol": symbol,
                "price": row['close'],
                "change": row['change_from_open'],
                "rvol": row['relative_volume_10d_calc'],
                "market_cap": row['market_cap_basic'],
                "perf_w": row['Perf.W'],
                "perf_1m": row['Perf.1M'],
                "perf_3m": row['Perf.3M'],
                "atr": row['ATR'],
                "volatility": row['Volatility.M'],
                "tier": tier,
                "grade": "S" if row['relative_volume_10d_calc'] > 3 else "A",
                "heat_score": min(100, int(row['relative_volume_10d_calc'] * 20)),
                "sortino": sortino_map.get(symbol, 0.0),
                "has_report": has_report,
                "updated_at": updated_at
            }

        raw_shield = [finalize_candidate(r, "SHIELD", sortino_map) for r in clean_shield]
        raw_sword = [finalize_candidate(r, "SWORD", sortino_map) for r in clean_sword]
        
        shield_candidates = [c for c in raw_shield if c is not None][:15]
        sword_candidates = [c for c in raw_sword if c is not None][:10]

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

        # --- DIFF CALCULATION ---
        prev_symbols = set()
        target_path = os.path.join(os.getcwd(), 'data', 'SCANNER_COMBAT_LIST.json')
        if os.path.exists(target_path):
            try:
                with open(target_path, 'r') as f:
                    old_state = json.load(f)
                    prev_symbols = {c['symbol'] for c in old_state.get('candidates', []) if 'symbol' in c}
            except: pass

        new_symbols = {c['symbol'] for c in dashboard_state['candidates']}
        added = len(new_symbols - prev_symbols)
        updated = len(new_symbols & prev_symbols)
        deleted = len(prev_symbols - new_symbols)
        total_found = len(new_symbols)

        # Persist to local data directory
        os.makedirs(os.path.dirname(target_path), exist_ok=True)
        with open(target_path, 'w') as f:
            json.dump(dashboard_state, f, indent=4)

        # Persist to Obsidian Vault for real-time UI rendering
        vault_path = r"c:\github\obsidian-vault\_cobalt\01_Transit\Buckets\SCANNER_RES_state.json"
        if os.path.exists(os.path.dirname(vault_path)):
            with open(vault_path, 'w') as f:
                json.dump(dashboard_state, f, indent=4)
            # print(f"Vault Sync Successful: {vault_path}")

        # [FINAL SUMMARY TELEMETRY]
        try:
            from src.config.vli import get_vli_path
            telemetry_file = get_vli_path("VLI_Raw_Telemetry.md")
            timestamp = datetime.now().strftime("[%H:%M:%S]")
            summary = f". Found {total_found} symbols. Added {added}; Updated {updated}; deleted {deleted}"
            with open(telemetry_file, "a", encoding="utf-8") as tf:
                tf.write(f"<span style='color: #888888'>{timestamp} [TV_SYNC]{summary}</span>\n")
                tf.flush()
        except Exception:
            pass

        print(f"Sync Successful: {summary}")

    except Exception as e:
        print(f"Sync Failed: {str(e)}")

if __name__ == "__main__":
    sync_vli_scanners()
