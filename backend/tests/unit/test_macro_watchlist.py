import asyncio
import os
import json
from unittest.mock import patch, MagicMock

# Create mock data
MOCK_MACRO_WATCHLIST = {
    "rows": [
        ["1", "SPY"],
        ["2", "QQQ"],
        ["3", "IWM"]
    ]
}

async def test_generate_macro_watchlist_report():
    print("Testing generate_macro_watchlist_report...")
    
    # Check if function exists
    try:
        from src.server.app import generate_macro_watchlist_report
    except ImportError:
        print("TEST FAILED: generate_macro_watchlist_report function does not exist in src.server.app.")
        exit(1)
        
    with patch('src.server.app.get_vli_path') as mock_get_vli_path:
        with patch('builtins.open', new_callable=MagicMock) as mock_open:
            import sys
            from unittest.mock import AsyncMock
            mock_smc = MagicMock()
            mock_smc.get_batch_smc_analysis.ainvoke = AsyncMock(return_value="# MOCK BATCH ANALYSIS REPORT")
            with patch.dict('sys.modules', {'src.tools.smc': mock_smc}):
                from src.server.app import generate_macro_watchlist_report
                
                # Setup mocks
                mock_get_vli_path.return_value = 'mock_macro_path.json'
                
                file_mock = MagicMock()
                file_mock.read.return_value = json.dumps(MOCK_MACRO_WATCHLIST)
                mock_open.return_value.__enter__.return_value = file_mock
                
                
                # Execute
                report_path = await generate_macro_watchlist_report()
                
                # Verify
                if not report_path:
                    print("TEST FAILED: generate_macro_watchlist_report did not return a path.")
                    exit(1)
                    
                if "macro_watchlist" not in report_path.lower():
                    print(f"TEST FAILED: Invalid report path returned: {report_path}")
                    exit(1)
                    
                mock_smc.get_batch_smc_analysis.ainvoke.assert_called_once()
                args, kwargs = mock_smc.get_batch_smc_analysis.ainvoke.call_args
                
                input_str = args[0] if args else kwargs.get("input", "")
                if isinstance(input_str, dict):
                    input_str = input_str.get("tickers_list", "")
                    
                print(f"Tool input: {input_str}")
                if "SPY" not in input_str or "QQQ" not in input_str or "IWM" not in input_str:
                    print("TEST FAILED: Tool was not called with the correct tickers.")
                    exit(1)
                    
                print("TEST PASSED: generate_macro_watchlist_report successfully generated the report.")
                exit(0)

if __name__ == "__main__":
    asyncio.run(test_generate_macro_watchlist_report())
