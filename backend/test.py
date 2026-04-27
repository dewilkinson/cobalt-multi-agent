import asyncio
from src.tools.scanner import trigger_morning_scan
print(asyncio.run(trigger_morning_scan.ainvoke({})))
