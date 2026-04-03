
import pytest
from src.server.app import extract_vli_logic, _vli_dynamic_panels

def test_extract_vli_logic_watchlist():
    # Reset global state for test
    global _vli_dynamic_panels
    _vli_dynamic_panels.clear()
    
    prompt = "Please create me a new watchlist window for Futures to monitor these shields."
    alerts = extract_vli_logic(prompt)
    
    # Verify dynamic panel was triggered
    assert any(p['id'] == "watch-futures-01" for p in _vli_dynamic_panels)
    print("✅ Logic Check: Futures Watchlist dynamic panel triggered successfully.")

def test_extract_vli_logic_tickers():
    prompt = "Monitoring $AAPL and $TSLA today."
    alerts = extract_vli_logic(prompt)
    
    symbols = [a['symbol'] for a in alerts]
    assert "AAPL" in symbols
    assert "TSLA" in symbols
    print("✅ Logic Check: Ticker extraction successful.")

if __name__ == "__main__":
    test_extract_vli_logic_watchlist()
    test_extract_vli_logic_tickers()
