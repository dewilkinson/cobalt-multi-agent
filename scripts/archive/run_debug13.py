import asyncio, sys, os, json
sys.path.append(os.path.abspath('backend'))
from src.tools.scanner import _run_activity_pulse_impl, NpEncoder

async def main():
    # Bypass the strategy config so everything passes
    config = {
        "price_min": 1.0,
        "price_max": 2000.0,
        "market_cap_min": 1,
        "market_cap_max": 5000_000_000_000,
        "float_min": 0,
        "float_max": 5000_000_000_000,
        "volume_hurdle": 0,
        "gap_min": -100.0,
        "gap_max": 100.0,
        "rvol_scout_min": 0.0,
        "rvol_strike_min": 0.0,
        "rvol_veto_max": 100.0,
        "sortino_hurdle": -100.0,
        "rs_hurdle": 0,
        "binary_veto_hours": 24
    }
    watchlist = json.dumps(["TSLA", "CELH", "NVDA", "MDB", "PLTR", "CRWD"])
    res = await _run_activity_pulse_impl(json.dumps(config), watchlist)
    data = json.loads(res)
    print("Candidates passed:")
    for c in data.get("candidates", []):
        print(f"[{c['symbol']}] Heat: {c.get('heat_score')}% | Rvol: {c.get('rvol')} | Gap: {c.get('gap')}% | Sortino: {c.get('sortino')} | Grade: {c.get('grade')}")

if __name__ == '__main__':
    asyncio.run(main())
