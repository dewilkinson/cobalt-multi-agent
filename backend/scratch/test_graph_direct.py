import asyncio
from src.graph.builder import build_graph

async def test():
    graph = build_graph()
    workflow_input = {
        "messages": [("user", "update ARM")],
        "steps_completed": 0,
    }
    config = {"configurable": {"thread_id": "test"}}
    try:
        final_state = await graph.ainvoke(workflow_input, config)
        for m in final_state["messages"]:
            print(f"[{m.name if hasattr(m, 'name') else 'user'}]: {m.content}")
    except Exception as e:
        print("ERROR:", e)

if __name__ == "__main__":
    asyncio.run(test())
