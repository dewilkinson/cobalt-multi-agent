import asyncio
import sys

sys.path.append("C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent\\backend")
from src.tools.finance import run_smc_analysis


async def main():
    try:
        res = await run_smc_analysis.ainvoke({"ticker": "ITA"})
        print(f"RESULT:\n{res}")
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    asyncio.run(main())
