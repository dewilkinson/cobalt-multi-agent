import asyncio
from src.server.app import post_vli_action_plan, VLIActionPlanRequest

async def run():
    req = VLIActionPlanRequest(text='test')
    try:
        await post_vli_action_plan(req, None, 'default')
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(run())
