import os
import shutil
import tempfile
import pytest
import json
import re

import sys
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..")))

from src.services.csv_importer import (
    parse_fidelity_orders,
    parse_fidelity_history,
    parse_fidelity_positions,
    parse_fidelity_closed_positions,
    parse_tradingview_paper_trading,
    process_dropzone_files,
    watch_dropzone_and_process
)
from src.services.brokerage_cache import BrokerageCache
import src.services.brokerage_cache
import src.config.loader

MOCK_TV_CSV = """Symbol,Side,Type,Quantity,Limit price,Stop price,Fill price,Status,Commission,Placing time,Closing time,Order ID,Level ID,Leverage,Margin
NASDAQ:PSNL,Sell,Market,600,,,12.69,Filled,,2026-06-25 15:28:58,2026-06-25 15:28:58,3224652629,,4:1,"1,903.50 USD"
NYSE:A,Buy,Market,50,,,138.2,Filled,,2026-06-25 10:30:28,2026-06-25 10:30:28,3223260204,,4:1,"1,727.50 USD"
"""

MOCK_FIDELITY_ORDERS_CSV = """Symbol,Action,Amount,Route,Status,Order Time,Account
AAPL,Buy,10,Auto,Filled at $150.00,09:45:00 AM 06-25-2026,mock-fidelity-1
"""

MOCK_FIDELITY_HISTORY_CSV = """Run Date,Account,Action,Symbol,Quantity,Price ($),Amount ($)
06/25/2026,Health Savings Account,YOU BOUGHT,AAPL,10,150.00,-1500.00
"""

def test_parse_tradingview_paper_trading():
    temp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(temp_dir, "paper-trading-order-history.csv")
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(MOCK_TV_CSV)
        
    try:
        res = parse_tradingview_paper_trading(csv_path)
        assert "TradingView Paper Stocks" in res
        acts = res["TradingView Paper Stocks"]
        assert len(acts) == 2
        assert acts[0]["symbol"]["symbol"] == "PSNL"
        assert acts[1]["symbol"]["symbol"] == "A"
    finally:
        shutil.rmtree(temp_dir)

def test_parse_tradingview_paper_trading_futures():
    temp_dir = tempfile.mkdtemp()
    csv_path = os.path.join(temp_dir, "futures.paper-trading-order-history.csv")
    
    mock_futures_csv = """Symbol,Side,Type,Quantity,Limit price,Stop price,Fill price,Status,Commission,Placing time,Closing time,Order ID,Level ID,Leverage,Margin
COMEX_MINI:MGC1!,Buy,Market,1,,,4014.2,Filled,,2026-06-25 01:13:56,2026-06-25 01:13:56,3221287730,,20:1,"2,007.10 USD"
CME:MBT1!,Sell,Market,1,,,61280,Filled,,2026-06-25 09:09:00,2026-06-25 09:09:00,3222550382,,20:1,"306.40 USD"
"""
    with open(csv_path, "w", encoding="utf-8") as f:
        f.write(mock_futures_csv)
        
    try:
        res = parse_tradingview_paper_trading(csv_path)
        assert "TradingView Paper Futures" in res
        acts = res["TradingView Paper Futures"]
        assert len(acts) == 2
        assert acts[0]["symbol"]["symbol"] == "/MGC"
        assert acts[1]["symbol"]["symbol"] == "/MBT"
    finally:
        shutil.rmtree(temp_dir)

def test_process_dropzone_unrecognized_file_ignored():
    temp_dropzone = tempfile.mkdtemp()
    
    # Drop unrecognized file
    unrecognized_csv = os.path.join(temp_dropzone, "unrecognized_file.csv")
    with open(unrecognized_csv, "w", encoding="utf-8") as f:
        f.write("Some,Header,Values\n1,2,3\n")
        
    try:
        msg = process_dropzone_files(optional_path=temp_dropzone)
        assert "No valid CSVs found to process" in msg
        # Assert unrecognized file remains in dropzone
        assert os.path.exists(unrecognized_csv)
        assert not os.path.exists(os.path.join(temp_dropzone, "archive", "unrecognized_file.csv"))
    finally:
        shutil.rmtree(temp_dropzone)

def test_process_dropzone_regex_routing(monkeypatch):
    temp_dropzone = tempfile.mkdtemp()
    temp_backup = tempfile.mkdtemp()
    temp_cache_dir = tempfile.mkdtemp()
    mock_cache_path = os.path.join(temp_cache_dir, "brokerage_cache.json")
    
    with open(mock_cache_path, "w", encoding="utf-8") as f:
        json.dump({
            "Rollover IRA *5513": {"activities": [], "positions": [], "closed_positions": []},
            "Health Savings Account *6937": {"activities": [], "positions": [], "closed_positions": []},
            "TradingView Paper Stocks": {"activities": [], "positions": [], "closed_positions": []},
            "TradingView Paper Futures": {"activities": [], "positions": [], "closed_positions": []}
        }, f)
        
    # Override paths / config using monkeypatch
    monkeypatch.setattr(src.services.brokerage_cache, "CACHE_FILE", mock_cache_path)
    monkeypatch.setattr(BrokerageCache, "get_backup_dir", lambda: temp_backup)
    
    mock_config = {
        "DROPZONE_ACCOUNTS": {
            "Rollover IRA *5513": ".*Rollover_IRA__5513.*\\.csv",
            "Health Savings Account *6937": ".*Health_Savings.*\\.csv",
            "TradingView Paper Stocks": ".*(?:stocks.*paper-trading-order-history|paper-trading-order-history.*stocks).*\\.csv",
            "TradingView Paper Futures": ".*(?:futures.*paper-trading-order-history|paper-trading-order-history.*futures).*\\.csv"
        }
    }
    monkeypatch.setattr(src.config.loader, "get_config", lambda: mock_config)
    
    # Drop recognized Rollover IRA Orders file
    orders_csv = os.path.join(temp_dropzone, "Orders_Rollover_IRA__5513.csv")
    with open(orders_csv, "w", encoding="utf-8") as f:
        f.write(MOCK_FIDELITY_ORDERS_CSV)
        
    # Drop recognized HSA History/Activity file
    history_csv = os.path.join(temp_dropzone, "Activity_Health_Savings.csv")
    with open(history_csv, "w", encoding="utf-8") as f:
        f.write(MOCK_FIDELITY_HISTORY_CSV)
        
    # Drop recognized TradingView Paper Stocks (Stocks token at the end)
    tv_stocks_csv = os.path.join(temp_dropzone, "paper-trading-order-history-stocks.csv")
    with open(tv_stocks_csv, "w", encoding="utf-8") as f:
        f.write(MOCK_TV_CSV)

    # Drop recognized TradingView Paper Futures (Futures token in front)
    tv_futures_csv = os.path.join(temp_dropzone, "futures.paper-trading-order-history.csv")
    with open(tv_futures_csv, "w", encoding="utf-8") as f:
        f.write("""Symbol,Side,Type,Quantity,Limit price,Stop price,Fill price,Status,Commission,Placing time,Closing time,Order ID,Level ID,Leverage,Margin
COMEX_MINI:MGC1!,Buy,Market,1,,,4014.2,Filled,,2026-06-25 01:13:56,2026-06-25 01:13:56,3221287730,,20:1,"2,007.10 USD"
""")
        
    try:
        msg = process_dropzone_files(optional_path=temp_dropzone)
        assert "Imported Orders" in msg
        assert "Imported History" in msg
        assert "Imported TradingView Paper Stocks" in msg
        assert "Imported TradingView Paper Futures" in msg
        
        # Verify routing in cache
        with open(mock_cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
            
        # Verify Rollover IRA got the orders
        rollover_acts = cache["Rollover IRA *5513"]["activities"]
        assert len(rollover_acts) == 1
        assert rollover_acts[0]["symbol"]["symbol"] == "AAPL"
        
        # Verify HSA got the history activities
        hsa_acts = cache["Health Savings Account *6937"]["activities"]
        assert len(hsa_acts) == 1
        assert hsa_acts[0]["symbol"]["symbol"] == "AAPL"
        
        # Verify TradingView Paper Stocks got the stocks
        tv_acts = cache["TradingView Paper Stocks"]["activities"]
        assert len(tv_acts) == 2
        assert any(a["symbol"]["symbol"] == "PSNL" for a in tv_acts)

        # Verify TradingView Paper Futures got the futures
        tc_acts = cache["TradingView Paper Futures"]["activities"]
        assert len(tc_acts) == 1
        assert any(a["symbol"]["symbol"] == "/MGC" for a in tc_acts)
        
    finally:
        shutil.rmtree(temp_dropzone)
        shutil.rmtree(temp_backup)
        shutil.rmtree(temp_cache_dir)

def test_watch_dropzone_and_process(monkeypatch):
    import src.services.csv_importer
    monkeypatch.setattr(src.services.csv_importer, "_last_dropzone_files", None)
    
    temp_dropzone = tempfile.mkdtemp()
    temp_backup = tempfile.mkdtemp()
    temp_cache_dir = tempfile.mkdtemp()
    mock_cache_path = os.path.join(temp_cache_dir, "brokerage_cache.json")
    
    with open(mock_cache_path, "w", encoding="utf-8") as f:
        json.dump({
            "TradingView Paper Stocks": {"activities": [], "positions": [], "closed_positions": []}
        }, f)
        
    monkeypatch.setattr(src.services.brokerage_cache, "CACHE_FILE", mock_cache_path)
    monkeypatch.setattr(BrokerageCache, "get_backup_dir", lambda: temp_backup)
    
    mock_config = {
        "DROPZONE_ACCOUNTS": {
            "TradingView Paper Stocks": ".*(?:stocks.*paper-trading-order-history|paper-trading-order-history.*stocks).*\\.csv"
        }
    }
    monkeypatch.setattr(src.config.loader, "get_config", lambda: mock_config)
    
    try:
        res = watch_dropzone_and_process(optional_path=temp_dropzone)
        assert "No files to process on initial run" in res
        
        stocks_csv = os.path.join(temp_dropzone, "paper-trading-order-history-stocks.csv")
        with open(stocks_csv, "w", encoding="utf-8") as f:
            f.write(MOCK_TV_CSV)
            
        res2 = watch_dropzone_and_process(optional_path=temp_dropzone)
        assert "Imported TradingView Paper Stocks" in res2
        
        res3 = watch_dropzone_and_process(optional_path=temp_dropzone)
        assert "No valid CSVs found to process" in res3 or "No changes" in res3
        
    finally:
        shutil.rmtree(temp_dropzone)
        shutil.rmtree(temp_backup)
        shutil.rmtree(temp_cache_dir)


def test_futures_multipliers():
    assert BrokerageCache.get_futures_multiplier("/MBT") == 0.1
    assert BrokerageCache.get_futures_multiplier("MBT1!") == 0.1
    assert BrokerageCache.get_futures_multiplier("/MGC") == 10.0
    assert BrokerageCache.get_futures_multiplier("MGC1!") == 10.0
    assert BrokerageCache.get_futures_multiplier("/MNK") == 0.5
    assert BrokerageCache.get_futures_multiplier("MNK") == 0.5
    assert BrokerageCache.get_futures_multiplier("/ES") == 50.0
    assert BrokerageCache.get_futures_multiplier("AAPL") == 1.0


def test_tradingview_paper_trading_prefixes(monkeypatch):
    import src.services.csv_importer
    from src.services.csv_importer import get_tradingview_csv_asset_type
    temp_dropzone = tempfile.mkdtemp()
    temp_backup = tempfile.mkdtemp()
    temp_cache_dir = tempfile.mkdtemp()
    mock_cache_path = os.path.join(temp_cache_dir, "brokerage_cache.json")
    
    with open(mock_cache_path, "w", encoding="utf-8") as f:
        json.dump({
            "TradingView Paper Stocks": {"activities": [], "positions": [], "closed_positions": []},
            "TradingView Paper Futures": {"activities": [], "positions": [], "closed_positions": []}
        }, f)
        
    monkeypatch.setattr(src.services.brokerage_cache, "CACHE_FILE", mock_cache_path)
    monkeypatch.setattr(BrokerageCache, "get_backup_dir", lambda: temp_backup)
    
    mock_config = {
        "DROPZONE_ACCOUNTS": {
            "TradingView Paper Trading": ".*paper-trading-order-history.*\\.csv"
        }
    }
    monkeypatch.setattr(src.services.csv_importer, "get_config", lambda: mock_config)
    
    stocks_csv = os.path.join(temp_dropzone, "paper-trading-order-history.csv")
    with open(stocks_csv, "w", encoding="utf-8") as f:
        f.write(MOCK_TV_CSV)
        
    futures_csv = os.path.join(temp_dropzone, "futures.paper-trading-order-history.csv")
    mock_futures_csv = """Symbol,Side,Type,Quantity,Limit price,Stop price,Fill price,Status,Commission,Placing time,Closing time,Order ID,Level ID,Leverage,Margin
COMEX_MINI:MGC1!,Buy,Market,1,,,4014.2,Filled,,2026-06-25 01:13:56,2026-06-25 01:13:56,3221287730,,20:1,"2,007.10 USD"
"""
    with open(futures_csv, "w", encoding="utf-8") as f:
        f.write(mock_futures_csv)
        
    try:
        assert get_tradingview_csv_asset_type(stocks_csv) == "STOCKS"
        assert get_tradingview_csv_asset_type(futures_csv) == "FUTURES"
        
        msg = process_dropzone_files(optional_path=temp_dropzone)
        assert "STOCKS_paper-trading-order-history.csv" in msg
        assert "FUTURES_futures.paper-trading-order-history.csv" in msg
        
        # Verify archive prefix
        assert os.path.exists(os.path.join(temp_dropzone, "archive", "STOCKS_paper-trading-order-history.csv"))
        assert os.path.exists(os.path.join(temp_dropzone, "archive", "FUTURES_futures.paper-trading-order-history.csv"))
        
        # Verify backup prefix
        backups = os.listdir(temp_backup)
        assert any(b.startswith("STOCKS_") for b in backups)
        assert any(b.startswith("FUTURES_") for b in backups)
        
        # Verify brokerage cache routing results
        with open(mock_cache_path, "r", encoding="utf-8") as f:
            cache = json.load(f)
        assert len(cache.get("TradingView Paper Stocks", {}).get("activities", [])) == 2
        assert len(cache.get("TradingView Paper Futures", {}).get("activities", [])) == 1
        assert len(cache.get("TradingView Paper Trading", {}).get("activities", [])) == 0
    finally:
        shutil.rmtree(temp_dropzone)
        shutil.rmtree(temp_backup)
        shutil.rmtree(temp_cache_dir)



