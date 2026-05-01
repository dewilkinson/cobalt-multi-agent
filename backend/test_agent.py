import asyncio
import sys
sys.path.append('c:\\github\\cobalt-multi-agent\\backend')
from src.server.app import _invoke_vli_agent

async def main():
    res, _ = await _invoke_vli_agent("analyze today's trades", thread_id='bg_test2')
    print("=== AGENT OUTPUT ===")
    print(res)

if __name__ == '__main__':
    asyncio.run(main())
