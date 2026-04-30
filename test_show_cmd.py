
import sys
import os
import re
import asyncio

query = 'show cpt report'
show_match = re.match(r'^(show|display)\s+(?:(report|news|quote)\s+(?:for\s+)?)?([a-zA-Z\.\=\^]+)(?:\s+(report|news|quote))?$', query)
print('Regex Match:', show_match.groups() if show_match else 'None')

sys.path.append(r'c:\github\cobalt-multi-agent\backend')
try:
    from src.graph.nodes.vli import vli_node
    from langchain_core.messages import HumanMessage
    
    async def main():
        state = {'messages': [HumanMessage(content='show cpt report')]}
        # config is required
        config = {'configurable': {'thread_id': 'test_123'}}
        result = await vli_node(state, config=config)
        print('VLI Spine Node Result:', result.update.keys() if hasattr(result, 'update') else result)
        if hasattr(result, 'update') and 'messages' in result.update:
            for m in result.update['messages']:
                print(m)

    asyncio.run(main())
except Exception as e:
    import traceback
    traceback.print_exc()

