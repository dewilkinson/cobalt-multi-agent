import asyncio
import logging

from langchain_core.messages import HumanMessage

from src.graph.builder import build_graph_with_memory

logging.basicConfig(level=logging.ERROR)


async def main():
    graph = build_graph_with_memory()
    config = {"configurable": {"thread_id": "test_imaging_123"}}

    inputs = {"messages": [HumanMessage(content="Use the imaging agent to look at my desktop. What apps are running?")], "auto_accepted_plan": True, "plan_iterations": 0}

    try:
        async for chunk in graph.astream(inputs, config=config, stream_mode="updates"):
            print(chunk)
    except Exception as e:
        print(f"Exception caught: {e}")


if __name__ == "__main__":
    asyncio.run(main())
