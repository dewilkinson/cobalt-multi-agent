import sys
import os

# Add src to path
sys.path.append(os.getcwd())

try:
    import yfinance as yf
    print(f"yfinance version: {yf.__version__}")
except ImportError as e:
    print(f"Error importing yfinance: {e}")

try:
    from langchain_core.tools import tool
    print("langchain_core tool imported successfully")
except ImportError as e:
    print(f"Error importing langchain_core: {e}")

try:
    from src.tools.finance import get_stock_quote
    print("get_stock_quote imported successfully")
    # quote = get_stock_quote("AAPL")
    # print(quote)
except ImportError as e:
    print(f"Error importing get_stock_quote from src.tools.finance: {e}")
except Exception as e:
    print(f"Error calling get_stock_quote: {e}")
