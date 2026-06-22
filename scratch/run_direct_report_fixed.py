import asyncio
import os
import sys

sys.path.append(os.path.abspath("backend"))

from dotenv import load_dotenv
load_dotenv("backend/.env")

# Force logging to console
import logging
logging.basicConfig(level=logging.INFO)

from src.server.app import _background_synthesis_task

async def main():
    date_str = "2026-06-10" # Today's date
    print('Running direct synthesis for June 10, 2026...')
    try:
        await _background_synthesis_task(
            text="Analyze today's executed trades and generate a detailed Daily Trading Report post-mortem.",
            image=None,
            direct_mode=False,
            reporter_llm_type='reasoning',
            vli_llm_type='basic',
            thread_id=f'POSTMORTEM_{date_str}',
            silent=False,
            snaptrade_settings=None
        )
        print('Done!')
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
