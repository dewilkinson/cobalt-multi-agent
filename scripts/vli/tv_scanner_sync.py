import json
import os
import sys
import asyncio
from datetime import datetime
import yfinance as yf
from tradingview_screener import Query, col

sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..', '..', 'backend')))
from src.tools.scanner import batch_fetch_sortino
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential

async def batch_fetch_news_sentiment(tickers: list) -> dict:
    import os
    api_key = os.environ.get("ALPHA_VANTAGE_API_KEY", "")
    if not api_key:
        return {}
    
    chunks = [tickers[i:i+10] for i in range(0, len(tickers), 10)]
    sentiment_map = {}
    
    @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
    async def fetch_chunk(chunk):
        url = f"https://www.alphavantage.co/query?function=NEWS_SENTIMENT&tickers={','.join(chunk)}&apikey={api_key}&limit=50"
        async with httpx.AsyncClient() as client:
            resp = await client.get(url, timeout=15.0)
            if resp.status_code == 200:
                if "Error Message" in resp.text or "Information" in resp.text:
                    raise RuntimeError("Alpha Vantage Rate Limit")
                data = resp.json()
                for item in data.get("feed", []):
                    for ts in item.get("ticker_sentiment", []):
                        tk = ts.get("ticker")
                        if tk in chunk:
                            score = float(ts.get("ticker_sentiment_score", 0))
                            if tk in sentiment_map:
                                sentiment_map[tk] = (sentiment_map[tk] + score) / 2
                            else:
                                sentiment_map[tk] = score
            
    await asyncio.gather(*(fetch_chunk(c) for c in chunks))
    return sentiment_map


def sync_vli_scanners():
    """
    Synchronizes the VLI Dashboard with real-time TradingView scanner results
    for Apex Shield and Apex Sword configurations.
    """
    print(f"[{datetime.now()}] Initiating TradingView Sync...")

    # [MINIMIZED] Immediate Telemetry for Start Sequence suppressed in favor of summary
    pass

    try:
        # Fetch SPY benchmark for RS Proxy
        spy_perf_3m = 0.0
        try:
            @retry(stop=stop_after_attempt(3), wait=wait_exponential(multiplier=1, min=2, max=10))
            def _get_spy():
                return yf.Ticker("SPY").history(period="3mo")
            spy_hist = _get_spy()
            if not spy_hist.empty:
                spy_perf_3m = ((spy_hist['Close'].iloc[-1] - spy_hist['Close'].iloc[0]) / spy_hist['Close'].iloc[0]) * 100
            print(f"SPY 3-Month Benchmark Performance: {spy_perf_3m:.2f}%")
        except Exception as e:
            print(f"Failed to fetch SPY benchmark for RS Proxy: {e}")
        # Field list for both scanners
        # Mapping to internal names for the dashboard
        fields = [
            'name', 'close', 'change', 'relative_volume_10d_calc', 'market_cap_basic',
            'Perf.W', 'Perf.1M', 'Perf.3M', 'ATR', 'Volatility.M', 'volume', 'SMA200', 'SMA50',
            'float_shares_outstanding', 'average_volume_30d_calc', 'Recommend.All', 'change_from_open', 'RSI',
            'relative_volume_intraday|5'
        ]
        # Set dynamic volume threshold based on time of day
        now = datetime.now()
        if now.hour < 10 or (now.hour == 10 and now.minute < 30):
            vol_shield_sniper = 100_000
            vol_sword = 50_000
        else:
            vol_shield_sniper = 1_000_000
            vol_sword = 500_000

        # --- 1. APEX SHIELD SCAN (Core / Institutional Leaders) ---
        shield_query = (Query()
            .set_markets('america')
            .select(*fields)
            .where(
                col('exchange').isin(['NASDAQ', 'NYSE', 'AMEX']),
                col('close') > 15,
                col('change') >= 3,
                col('market_cap_basic') > 300_000_000,
                col('volume') > vol_shield_sniper,
                col('float_shares_outstanding') > 100_000_000,
                col('ATR') > 1,
                col('close') > col('SMA200'),
                col('Volatility.M') > 2
            )
            .order_by('relative_volume_10d_calc', ascending=False))

        # --- 2. APEX SWORD SCAN (Satellite / High-Volatility Runners) ---
        sword_query = (Query()
            .set_markets('america')
            .select(*fields)
            .where(
                col('exchange').isin(['NASDAQ', 'NYSE', 'AMEX']),
                col('type').isin(['stock', 'fund']),
                col('close').between(1, 20),
                col('market_cap_basic').between(100_000_000, 2_000_000_000),
                col('volume') > vol_sword,
                col('float_shares_outstanding') < 100_000_000,
                col('ATR') > 0.75,
                col('close') > col('SMA50'),
                col('Volatility.M') > 5,
                col('relative_volume_intraday|5') > 2,
                col('change') > 3,
                col('Recommend.All') >= 0.1
            )
            .order_by('relative_volume_10d_calc', ascending=False))

        # --- 3. SORTINO SNIPER SCAN (Momentum & SMC) ---
        sniper_query = (Query()
            .set_markets('america')
            .select(*fields)
            .where(
                col('exchange').isin(['NASDAQ', 'NYSE', 'AMEX']),
                col('type').isin(['stock', 'fund']),
                col('close') >= 5,
                col('change') >= 3,
                col('volume') > vol_shield_sniper,
                col('market_cap_basic').between(300_000_000, 2_000_000_000),
                col('float_shares_outstanding').between(20_000_000, 100_000_000),
                col('relative_volume_intraday|5') >= 1.2
            )
            .order_by('relative_volume_intraday|5', ascending=False))


        # Determine Active Strategy
        active_strategy = ""
        config_path = r"c:\github\obsidian-vault\_cobalt\vli_session_config.json"
        if os.path.exists(config_path):
            try:
                with open(config_path, "r", encoding="utf-8") as cf:
                    active_strategy = json.load(cf).get("active_strategy", "").lower()
            except: pass

        import pandas as pd
        empty_df = pd.DataFrame(columns=['name', 'close', 'change', 'volume', 'relative_volume_intraday|5', 'market_cap_basic'])

        # Execute Queries
        shield_df = shield_query.get_scanner_data()[1]
        sword_df = sword_query.get_scanner_data()[1]
        sniper_df = sniper_query.get_scanner_data()[1]

        raw_all = shield_df['name'].tolist() + sword_df['name'].tolist() + sniper_df['name'].tolist()
        
        # [MINIMIZED] Telemetry for query completion suppressed
        pass

        removed_trace = []

        # Process and map for VLI Dashboard
        def map_candidate(row, tier, spy_benchmark, track_spy):
            symbol = row['name']
            
            # [HARDENING] Strict sanitization
            if any(char in symbol for char in ['.', '-', '/', '^', '=']):
                removed_trace.append(f"    Removed: **{symbol}** (Invalid Characters)")
                return None
            if len(symbol) > 4 and symbol[-1] in ['W', 'U', 'R', 'P']:
                removed_trace.append(f"    Removed: **{symbol}** (Preferred/Warrant Filter)")
                return None
            
            # [RS PROXY FILTER] - Moved to Frontend for per-window isolation
            return row

        # Load Scanner Settings
        track_spy = False
        try:
            settings_path = os.path.join(os.path.dirname(__file__), "..", "..", "backend", "data", "scanner_settings.json")
            if os.path.exists(settings_path):
                with open(settings_path, "r", encoding="utf-8") as f:
                    track_spy = json.load(f).get("track_spy", False)
        except Exception as e:
            print(f"Error loading scanner settings: {e}")

        clean_shield = [r for r in (map_candidate(r, "SHIELD", spy_perf_3m, track_spy) for _, r in shield_df.iterrows()) if r is not None]
        clean_sword = [r for r in (map_candidate(r, "SWORD", spy_perf_3m, track_spy) for _, r in sword_df.iterrows()) if r is not None]
        clean_sniper = [r for r in (map_candidate(r, "SNIPER", spy_perf_3m, track_spy) for _, r in sniper_df.iterrows()) if r is not None]

        # [MINIMIZED] Sanitization Trace suppressed
        pass

        # Fetch Sortino for surviving candidates
        all_symbols = [r['name'] for r in clean_shield] + [r['name'] for r in clean_sword] + [r['name'] for r in clean_sniper]
        
        # [MINIMIZED] Sortino calculation telemetry suppressed
        pass
            
        print(f"Fetching localized Sortino ratios for {len(all_symbols)} candidates...")
        sortino_map = asyncio.run(batch_fetch_sortino(all_symbols, period="20d"))
        sentiment_map = asyncio.run(batch_fetch_news_sentiment(all_symbols))

        def finalize_candidate(row, tier, sortino_map, sentiment_map):
            symbol = row['name']
            report_path = os.path.join(os.getcwd(), 'data', 'reports', f'analyze_{symbol.lower()}.md')
            
            # [HARDENING] Strict sanitization to prevent preferred/warrants/units and hallucinated strings
            if any(char in symbol for char in ['.', '-', '/', '^', '=']):
                removed_trace.append(f"    Removed: **{symbol}** (Invalid Characters)")
                return None
            if len(symbol) > 4 and symbol[-1] in ['W', 'U', 'R', 'P']:
                removed_trace.append(f"    Removed: **{symbol}** (Preferred/Warrant Filter)")
                return None

            sortino = sortino_map.get(symbol, 0.0)
            sentiment_score = sentiment_map.get(symbol, 0.0)
            
            # --- ADVANCED QUANTITATIVE GRADING ---
            # Default passing candidates start at a C grade (40 points)
            heat = 40.0
            
            rvol = row.get('relative_volume_10d_calc', 0)
            if rvol > 1.0:
                heat += min(20, (rvol - 1.0) * 15)
                
            if sortino > 0:
                heat += min(30, sortino * 5)
            else:
                heat -= min(20, abs(sortino) * 10)
                
            perf_w = row.get('Perf.W')
            perf_1m = row.get('Perf.1M')
            if perf_1m is not None:
                if perf_1m > 0:
                    heat += min(20, perf_1m)
                else:
                    heat -= min(20, abs(perf_1m))
                    
            if sentiment_score > 0.15:
                heat += 15.0
            elif sentiment_score < -0.15:
                heat -= 15.0
                    
            heat = max(0, min(100, int(heat)))
            
            if heat >= 90: grade = "S"
            elif heat >= 80: grade = "A+"
            elif heat >= 70: grade = "A"
            elif heat >= 60: grade = "B+"
            elif heat >= 50: grade = "B"
            elif heat >= 40: grade = "C"
            elif heat >= 30: grade = "C-"
            elif heat >= 20: grade = "D"
            else: grade = "F"
            
            if grade in ["S", "A+"] and sentiment_score <= 0.05:
                grade = "A"
                heat = min(heat, 79.0)
            
            # Hard fails for falling knives
            if perf_1m is not None and perf_w is not None:
                if perf_1m < -10 and perf_w < -5:
                    grade = "F"
                    heat = min(heat, 15)
                    
            # Minimum passing grade is C-
            if heat < 30 or grade in ["D", "F"]:
                removed_trace.append(f"    Removed: **{symbol}** (Failed Quantitative Grading - Final Grade: {grade})")
                return None
                
            report_path = os.path.join(os.getcwd(), 'backend', 'data', 'reports', f'analyze_{symbol.lower()}.md')
            updated_at = None
            has_report = False
            if os.path.exists(report_path):
                mtime = datetime.fromtimestamp(os.path.getmtime(report_path))
                updated_at = mtime.isoformat()
                if mtime.date() == datetime.now().date():
                    has_report = True
                    
                # Evaluate LLM Report Verdict Override
                try:
                    with open(report_path, "r", encoding="utf-8") as rf:
                        report_text = rf.read()
                        if "[FAIL]" in report_text or "**FAIL**" in report_text or "[UNRATED]" in report_text or "UNRATED/FAIL" in report_text:
                            removed_trace.append(f"    Removed: **{symbol}** (Failed LLM Structural Audit - Verdict: FAIL)")
                            return None
                except Exception:
                    pass
                    
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
                "grade": grade,
                "heat_score": heat,
                "sortino": sortino,
                "has_report": has_report,
                "updated_at": updated_at
            }

        raw_shield = [finalize_candidate(r, "SHIELD", sortino_map, sentiment_map) for r in clean_shield]
        raw_sword = [finalize_candidate(r, "SWORD", sortino_map, sentiment_map) for r in clean_sword]
        raw_sniper = [finalize_candidate(r, "SNIPER", sortino_map, sentiment_map) for r in clean_sniper]
        
        shield_candidates = [c for c in raw_shield if c is not None]
        sword_candidates = [c for c in raw_sword if c is not None]
        sniper_candidates = [c for c in raw_sniper if c is not None]

        # Deduplicate candidates across tiers (Priority: SNIPER > SWORD > SHIELD)
        seen_symbols = set()
        deduped_candidates = []
        for c in (sniper_candidates + sword_candidates + shield_candidates):
            if c['symbol'] not in seen_symbols:
                seen_symbols.add(c['symbol'])
                deduped_candidates.append(c)

        # [HARDENING] Rank-Based Uniform Percentile Curve Grading
        # Override the initial absolute grading gate with a true bell curve
        deduped_candidates.sort(key=lambda x: -x.get("sortino", 0.0))
        n = len(deduped_candidates)
        for i, v in enumerate(deduped_candidates):
            if n > 1:
                percentile = (n - 1 - i) / (n - 1)
            else:
                percentile = 1.0
            
            heat_score = int(40 + (percentile * 60))
            if heat_score >= 95: grade = "S"
            elif heat_score >= 90: grade = "A+"
            elif heat_score >= 82: grade = "A"
            elif heat_score >= 75: grade = "B+"
            elif heat_score >= 65: grade = "B"
            elif heat_score >= 58: grade = "C+"
            elif heat_score >= 50: grade = "C"
            elif heat_score >= 35: grade = "D"
            else: grade = "F"
            
            v["grade"] = grade
            v["heat_score"] = heat_score

        # Enforce grade caps (max 3 S grades, max 4 A/A+ grades)
        s_count = 0
        a_count = 0
        for v in deduped_candidates:
            if v["grade"] == "S":
                if s_count >= 3:
                    v["grade"] = "A+"
                else:
                    s_count += 1
            
            if v["grade"] in ["A+", "A"]:
                if a_count >= 4:
                    v["grade"] = "B+"
                else:
                    a_count += 1

        # Final Dashboard State
        dashboard_state = {
            "pulse_mode": "TradingView (HIGH-FIDELITY)",
            "total_pulsed": len(deduped_candidates),
            "candidates_passed": len(deduped_candidates),
            "candidates": deduped_candidates,
            "metadata": {
                "last_sync": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
                "shield_count": len(shield_candidates),
                "sword_count": len(sword_candidates),
                "sniper_count": len(sniper_candidates),
                "spy_benchmark": spy_perf_3m,
                "status": "active"
            }
        }

        # --- DIFF CALCULATION ---
        prev_symbols = set()
        target_path = os.path.join(os.getcwd(), 'backend', 'data', 'STRIKE_LIST.json')
        if not os.path.exists(os.path.dirname(target_path)):
            # Fallback if run directly from backend folder
            target_path = os.path.join(os.getcwd(), 'data', 'STRIKE_LIST.json')
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

        # Archive scan list daily details
        try:
            from src.tools.scanner import update_scanner_archive
            update_scanner_archive(dashboard_state.get("candidates", []))
        except Exception as e:
            print(f"Failed to archive scan lists: {e}")

        # Persist to Obsidian Vault for real-time UI rendering
        try:
            from src.config.vli import get_vli_path
            vault_path = get_vli_path(os.path.join("01_Transit", "Buckets", "STRIKE_RES_state.json"))
        except:
            vault_path = r"c:\github\obsidian-vault\_cobalt\01_Transit\Buckets\STRIKE_RES_state.json"
            
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

        # [MACRO WATCHLIST SYNC]
        try:
            from src.tools.finance import get_macro_symbols
            print("Syncing Macro Watchlist...")
            tool_fn = getattr(get_macro_symbols, "coroutine", getattr(get_macro_symbols, "func", None))
            if tool_fn:
                asyncio.run(tool_fn(fast_update=False))
            else:
                get_macro_symbols.invoke({"fast_update": False})
            print("Macro Watchlist Sync Successful")
        except Exception as e:
            print(f"Macro Watchlist Sync Failed: {e}")

        # [WATCHLIST EXPORT]
        try:
            print("Exporting TradingView Watchlists...")
            proj_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".."))
            if proj_root not in sys.path:
                sys.path.append(proj_root)
            from scripts.utils.export_tradingview_watchlists import main as run_export
            run_export()
            print("TradingView Watchlists Export Successful")
        except Exception as e:
            print(f"TradingView Watchlists Export Failed: {e}")

        print(f"Sync Successful: {summary}")

    except Exception as e:
        print(f"Sync Failed: {str(e)}")

if __name__ == "__main__":
    sync_vli_scanners()
