import asyncio
import traceback
from langchain_core.messages import HumanMessage
from src.graph.builder import build_graph_with_memory
from langchain_core.runnables import RunnableConfig

async def main():
    try:
        print("Building graph...")
        graph = build_graph_with_memory()
        
        print("Invoking graph...")
        config = RunnableConfig(configurable={"thread_id": "test_scanner_123"}, recursion_limit=50)
        
        state = {
            "messages": [HumanMessage(content="Execute market scanner")],
            "direct_mode": False
        }
        
        final_state = await graph.ainvoke(state, config=config)
        print("Graph execution successful.")
        
        # Examine the output of the final message
        for m in final_state["messages"][-5:]:
            print(f"\n--- {m.type.upper()} ---")
            print(m.content)

        
    except Exception as e:
        print(f"\nCaught Exception: {type(e).__name__}: {e}")
        print("\nTraceback:")
        traceback.print_exc()

if __name__ == "__main__":
    asyncio.run(main())
