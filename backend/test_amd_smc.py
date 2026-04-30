import asyncio

from src.tools.finance import run_smc_analysis


async def test():
    f = getattr(run_smc_analysis, "coroutine", None)
    res = await f("AMD", "1d")
    with open("smc_output.txt", "w", encoding="utf-8") as file:
        file.write(res)


if __name__ == "__main__":
    asyncio.run(test())
