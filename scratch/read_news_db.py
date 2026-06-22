import os
import sys
import json

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

from src.config.database import get_session_local, PersistentCache

def main():
    SessionLocal = get_session_local()
    with SessionLocal() as db:
        tickers = ["INTC", "AMAT", "ARM", "CRWD", "CRWV"]
        for t in tickers:
            print(f"\n================ DB DATA FOR {t} ================")
            cache_objs = db.query(PersistentCache).filter(
                PersistentCache.ticker == t
            ).all()
            if not cache_objs:
                print("No database cache objects found.")
                continue
            for obj in cache_objs:
                print(f"Resource Type: {obj.resource_type} | Timeframe: {obj.timeframe} | Updated: {obj.created_at}")
                try:
                    data = json.loads(obj.data)
                    if isinstance(data, dict):
                        print("Keys:", list(data.keys()))
                    else:
                        print("Data preview:", str(data)[:500])
                except Exception:
                    print("Data preview (raw):", obj.data[:500])

if __name__ == "__main__":
    main()
