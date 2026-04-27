import asyncio
import sys
import os
import logging

sys.path.append(os.path.dirname(__file__))

from src.graph.builder import build_graph

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    graph = build_graph()
    from langchain_core.messages import HumanMessage
    state = {'ticker': 'ARM', 'messages': [HumanMessage(content='Update the intelligence report for ARM.')], 'verbosity': 2}
    config = {'configurable': {'thread_id': 'test-arm'}}
    
    print('Starting graph for ARM...')
    try:
        async for event in graph.astream(state, config):
            print("EVENT RECIEVED:", event.keys() if isinstance(event, dict) else event)
    except Exception as e:
        print(f'Error: {e}')

if __name__ == '__main__':
    asyncio.run(main())
