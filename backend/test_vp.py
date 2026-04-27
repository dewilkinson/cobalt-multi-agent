import asyncio
import sys
import os
sys.path.append(os.path.dirname(__file__))
from src.tools import get_volume_profile
async def main():
    print(await get_volume_profile.ainvoke({'ticker': 'STM'}))
if __name__ == '__main__':
    asyncio.run(main())
