import asyncio
import os
from datetime import datetime
import sys
import logging

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)

sys.path.append(os.getcwd())
from src.server.app import _background_synthesis_task

async def main():
    date_str = datetime.now().strftime('%Y-%m-%d')
    print('Running direct synthesis...')
    try:
        await _background_synthesis_task(
            text='Analyze today\'s executed trades and generate a detailed Daily Trading Report post-mortem.',
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
        print(f'Error: {e}')

if __name__ == '__main__':
    asyncio.run(main())
