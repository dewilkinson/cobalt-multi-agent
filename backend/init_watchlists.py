import os
import sys

# Setup environment
os.environ["OBSIDIAN_VAULT_PATH"] = "c:/github/obsidian-vault"
sys.path.append("C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend")

from langchain_core.runnables import RunnableConfig

from src.tools.portfolio import update_watchlist

config = RunnableConfig(configurable={})

lists = [
    {"name": "Index", "tickers": ["SPY", "QQQ", "IWM", "DIA"], "metadata": {"Sector": "Indices", "Theme": "Market Averages"}},
    {"name": "Futures", "tickers": ["ES=F", "NQ=F", "CL=F", "GC=F"], "metadata": {"Sector": "Futures", "Theme": "Global Macro"}},
    {"name": "Daily", "tickers": ["AAPL", "NVDA", "TSLA"], "metadata": {"Sector": "Tech", "Type": "Sword", "Conviction": "High"}},
    {"name": "Energy", "tickers": ["XOM", "CVX", "OXY", "ET"], "metadata": {"Sector": "Energy", "Type": "Shield", "Conviction": "Medium"}},
    {"name": "Bio", "tickers": ["VRTX", "AMGN", "REGN"], "metadata": {"Sector": "Biotech", "Type": "Sword", "Conviction": "Speculative"}},
]

for l in lists:
    res = update_watchlist.func(tickers=l["tickers"], name=l["name"], action="add", metadata=l["metadata"], config=config)
    print(res)
