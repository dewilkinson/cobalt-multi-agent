import asyncio
import sys
import os
sys.path.append(os.path.abspath('backend'))
from src.graph.builder import build_graph
from langchain_core.messages import HumanMessage

async def main():
    graph = build_graph()
    config = {'configurable': {'thread_id': 'test1'}}
    inputs = {'messages': [HumanMessage(content='get news sentiment for TSLA')]}
    try:
        async for event in graph.astream(inputs, config, stream_mode='values'):
            if 'messages' in event:
                print(event['messages'][-1].content[:200] if hasattr(event['messages'][-1], 'content') else event['messages'][-1][:200])
    except Exception as e:
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    asyncio.run(main())
