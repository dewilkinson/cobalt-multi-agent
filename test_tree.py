import sys, os, asyncio
sys.path.insert(0, os.path.join(os.getcwd(), 'backend'))
from src.server.app import get_artifacts_tree
async def test():
    try:
        res = await get_artifacts_tree()
        print('OK')
    except Exception as e:
        import traceback
        traceback.print_exc()
asyncio.run(test())
