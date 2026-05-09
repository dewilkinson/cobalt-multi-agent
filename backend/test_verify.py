import asyncio
import yfinance as yf

async def verify_candidate(c):
    ticker = c["symbol"]
    try:
        ticker_obj = yf.Ticker(ticker)
        info = await asyncio.to_thread(lambda: ticker_obj.info)
        price = info.get("preMarketPrice") or info.get("postMarketPrice") or info.get("currentPrice") or info.get("regularMarketPrice") or 0.0
        
        try:
            fast = ticker_obj.fast_info
            volume = fast.last_volume or info.get("volume") or 0
            m_cap = fast.market_cap or info.get("marketCap") or 0
            if not price:
                price = fast.last_price or fast.previous_close or 0.0
        except Exception as e:
            print("Fast info failed:", e)
            volume = info.get("volume") or 0
            m_cap = info.get("marketCap") or 0
        
        beta = info.get("beta") or 1.0
        div_yield = info.get("dividendYield") or 0.0
        f_shares = info.get("floatShares") or 0
        
        c_sortino = 5.0

        if c_sortino < 0.0:
            print("Rejected:", ticker)
            return None
        
        effective_hurdle = 2.0
        grade = "S" if c_sortino >= effective_hurdle * 1.5 else ("A" if c_sortino >= effective_hurdle * 1.2 else "B")
        
        return {
            **c,
            "price": round(price, 2),
            "volume": volume,
            "beta": round(beta, 2),
            "dividend_yield": round(div_yield * 100, 2),
            "float": f_shares,
            "market_cap": m_cap,
            "sortino": c_sortino,
            "tier": "SHIELD",
            "grade": grade,
        }
    except Exception as e:
        print("Verification failed for", ticker, ":", e)
        import traceback
        traceback.print_exc()
        return None

async def main():
    res = await verify_candidate({"symbol": "ITA"})
    print("Result:", res)

if __name__ == "__main__":
    asyncio.run(main())
