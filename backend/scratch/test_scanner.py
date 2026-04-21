import asyncio
import json
import logging
from src.tools.scanner import build_session_watchlist, run_activity_pulse

logging.basicConfig(level=logging.INFO)

async def test_scanner():
    print("=== COBALT MULTI-AGENT MARKET SCANNER DIAGNOSTIC ===")
    
    strategy_config = json.dumps({
        "price_min": 10.0,
        "price_max": 200.0,
        "rvol_strike_min": 1.5,
    })

    print(f"\n[1] Executing Phase 1: build_session_watchlist")
    print(f"Strategy constraints: {strategy_config}")
    
    # Run watchlist filter
    wl_json = await build_session_watchlist.ainvoke({"strategy_config": strategy_config})
    wl_result = json.loads(wl_json)
    print(f"\nPhase 1 Result:")
    print(json.dumps(wl_result, indent=2))
    
    watchlist = wl_result.get("watchlist", [])
    
    if watchlist:
        print(f"\n[2] Executing Phase 2: run_activity_pulse on {len(watchlist)} candidates")
        watchlist_json = json.dumps(watchlist)
        
        pulse_json = await run_activity_pulse.ainvoke({"strategy_config": strategy_config, "watchlist": watchlist_json})
        pulse_result = json.loads(pulse_json)
        print(f"\nPhase 2 Result:")
        print(json.dumps(pulse_result, indent=2))
    else:
        print("\n[!] Watchlist empty, skipping activity pulse.")
        
if __name__ == "__main__":
    asyncio.run(test_scanner())
