import asyncio
import sys
import os
import logging
import faulthandler
import signal

# Register signal handler to dump traceback on SIGINT (Ctrl+C)
# On Windows we can't easily send SIGINT programmatically to a subprocess, 
# but we can just use a threading timer to dump traceback!
import threading
import traceback

def dump_trace():
    print("DUMPING TRACEBACK")
    for thread_id, frame in sys._current_frames().items():
        print(f"\\n--- Thread {thread_id} ---")
        traceback.print_stack(frame)
    os._exit(1)

# Dump trace after 5 seconds if hanging
threading.Timer(5.0, dump_trace).start()

sys.path.append(os.path.dirname(__file__))
from src.tools.news import get_ticker_news
from src.tools.finance import get_stock_quote

async def main():
    print('Calling get_ticker_news NVDA')
    try:
        res = await get_ticker_news.ainvoke({'subject': 'NVDA', 'refresh': True})
        print('News Res Length:', len(str(res)))
    except Exception as e:
        print('News Error:', e)
        
    print('Calling get_stock_quote NVDA')
    try:
        res2 = await get_stock_quote.ainvoke({'ticker': 'NVDA', 'force_refresh': True})
        print('Quote Res Length:', len(str(res2)))
    except Exception as e:
        print('Quote Error:', e)

if __name__ == '__main__':
    asyncio.run(main())
