import asyncio, traceback
from src.server.app import _invoke_vli_agent
async def test():
    try:
        res, state = await _invoke_vli_agent(text='clear scan', image=None, direct_mode=True, raw_data_mode=False, reporter_llm_type="core", vli_llm_type="reasoning", thread_id='1234')
        print(res[:200])
    except Exception as e:
        print('FAILED:', e)
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(test())
