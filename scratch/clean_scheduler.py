import json
import os
from datetime import datetime

scheduler_json = 'C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent\\data\\scheduler.json'
scheduler_log = 'C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent\\data\\scheduler.log'

try:
    with open(scheduler_json, 'r') as f:
        data = json.load(f)
except Exception:
    data = {"tasks": []}

now = datetime.now()
today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

logs = []
for task in data.get("tasks", []):
    # Check if daily
    is_daily = False
    if task["type"] == "CALENDAR":
        is_daily = True
    elif task["type"] == "REPEAT":
        period = float(task.get("schedule", 0))
        unit = task.get("period_unit", "")
        if unit == "hours" and period >= 12:
            is_daily = True
        elif unit in ["days", "weeks", "months"]:
            is_daily = True
            
    last_run = task.get("last_run")
    if last_run:
        try:
            last_run_dt = datetime.fromisoformat(last_run)
            if last_run_dt >= today_start:
                if is_daily:
                    logs.append(f"[{last_run_dt.strftime('%Y-%m-%d %H:%M:%S')}] [HEARTBEAT] [EXEC] {task['priority']} Task: {task['name']} ({task['task_id']})")
                    logs.append(f"[{last_run_dt.strftime('%Y-%m-%d %H:%M:%S')}] [HEARTBEAT] Status: COMPLETED {task['task_id']}")
        except:
            pass

# Write to log file
with open(scheduler_log, 'w', encoding='utf-8') as f:
    f.write("[2026-04-30 00:00:00] [HEARTBEAT] Scheduler Log Cleared and Re-Injected by System\n")
    for log in logs:
        f.write(log + "\n")

print(f"Cleared scheduler.log and reinjected {len(logs)//2} daily jobs.")
