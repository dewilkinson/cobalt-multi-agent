import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
    
import asyncio
from src.tools.finance import run_smc_analysis

async def main():
    try:
        print("Starting ITA analysis...")
        res = await run_smc_analysis.ainvoke({'ticker': 'ITA'})
        print("Done:")
        print(repr(res))
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
