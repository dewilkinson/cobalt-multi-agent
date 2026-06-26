import asyncio
import os
from datetime import datetime
import sys

sys.path.append(os.getcwd())
from src.server.app import _background_synthesis_task

async def main():
    date_str = None
    for arg in sys.argv:
        if arg.startswith("--date="):
            date_str = arg.split("=")[1]
        elif arg == "--date" and len(sys.argv) > sys.argv.index(arg) + 1:
            date_str = sys.argv[sys.argv.index(arg) + 1]
            
    if not date_str:
        date_str = os.environ.get("VLI_REPORT_DATE")
        
    if not date_str:
        date_str = datetime.now().strftime('%Y-%m-%d')
        
    # Also set VLI_REPORT_DATE in environment so tools downstream can read it
    os.environ["VLI_REPORT_DATE"] = date_str
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
