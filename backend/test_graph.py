import sys
if sys.platform == 'win32' and hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
    sys.stderr.reconfigure(encoding='utf-8')
import asyncio
import os
sys.path.append('c:\\github\\cobalt-multi-agent\\backend')
from src.server.app import _invoke_vli_agent

async def main():
    try:
        res = await _invoke_vli_agent("run smc analysis on ITA", direct_mode=False)
        print("RESULT:")
        print(res)
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
