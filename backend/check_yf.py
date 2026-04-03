import src.tools.finance as finance_module
from unittest.mock import patch
print("Has yf:", hasattr(finance_module, 'yf'))
print("Has yfinance:", hasattr(finance_module, 'yfinance'))
print(dir(finance_module))
