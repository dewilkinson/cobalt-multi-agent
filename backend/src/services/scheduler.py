"""
PROJECT COBALT: CORE RESOURCE TYPE
RESOURCE: Cobalt Scheduler Engine
VERSION: 2.0.0

The Cobalt Scheduler provides a centralized registry for rhythmic tasks 
(REPEAT, ONE_SHOT, CALENDAR) with a sequential multi-queue priority system.
"""

import json
import os
import subprocess
import asyncio
import logging
import time
import sys
from datetime import datetime, timedelta
from typing import Dict, List, Any, Callable, Optional
from dataclasses import dataclass, field
from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from apscheduler.triggers.interval import IntervalTrigger
from apscheduler.triggers.date import DateTrigger
import pandas as pd

from src.config.vli import get_scheduler_json_path, get_scheduler_log_path

logger = logging.getLogger(__name__)

@dataclass
class ScheduledTask:
    task_id: str
    name: str
    type: str # REPEAT, ONE_SHOT, CALENDAR
    priority: str # CRITICAL, HIGH, NORMAL, LOW, BACKGROUND
    schedule: Any
    period_unit: Optional[str] = None
    repeat_count: int = 0
    command: Optional[str] = None
    callback: Optional[Callable] = None
    status: str = "ACTIVE"
    last_run: Optional[str] = None
    current_run_count: int = 0
    start_time: Optional[float] = None

class CobaltScheduler:
    def __init__(self):
        self.scheduler = BackgroundScheduler()
        self.registry_path = get_scheduler_json_path()
        self.log_file = get_scheduler_log_path()
        
        # Priority Queues
        self.queues = {
            "CRITICAL": asyncio.Queue(),
            "HIGH": asyncio.Queue(),
            "NORMAL": asyncio.Queue(),
            "LOW": asyncio.Queue(),
            "BACKGROUND": asyncio.Queue()
        }
        
        self.tasks: Dict[str, ScheduledTask] = {}
        self.executing_tasks: Dict[str, ScheduledTask] = {}
        self.pending_tasks: set[str] = set()
        self._is_running = False
        self._worker_task = None
        self.loop = None # Captured at start()
        
        # Platform Idle State
        self.platform_idle = True # Should be updated by app.py

    def log(self, message, level=logging.INFO):
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        entry = f"[{timestamp}] [HEARTBEAT] {message}"
        if level == logging.ERROR:
            logger.error(entry)
        else:
            logger.info(entry)
            
        os.makedirs(os.path.dirname(self.log_file), exist_ok=True)
        try:
            with open(self.log_file, "a", encoding="utf-8") as f:
                f.write(entry + "\n")
        except Exception as e:
            logger.error(f"Failed to write to scheduler log: {e}")

    def load_from_json(self):
        """Loads tasks from scheduler.json. External tasks only."""
        if not os.path.exists(self.registry_path):
            self.log("No scheduler registry found. Initializing.")
            self._save_registry()
            return

        try:
            with open(self.registry_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                for task_data in data.get("tasks", []):
                    t_id = task_data["task_id"]
                    if t_id in self.tasks:
                        self.tasks[t_id].last_run = task_data.get("last_run")
                        self.tasks[t_id].current_run_count = task_data.get("current_run_count", 0)
                    else:
                        task = ScheduledTask(**task_data)
                        self.tasks[t_id] = task
                        self._schedule_in_engine(task)
        except Exception as e:
            self.log(f"Failed to load registry: {e}", level=logging.ERROR)

    def _save_registry(self):
        os.makedirs(os.path.dirname(self.registry_path), exist_ok=True)
        serializable_tasks = []
        for task in self.tasks.values():
            t_dict = {
                "task_id": task.task_id,
                "name": task.name,
                "type": task.type,
                "priority": task.priority,
                "schedule": task.schedule,
                "period_unit": task.period_unit,
                "repeat_count": task.repeat_count,
                "command": task.command,
                "status": task.status,
                "last_run": task.last_run,
                "current_run_count": task.current_run_count
            }
            serializable_tasks.append(t_dict)
        
        try:
            with open(self.registry_path, "w", encoding="utf-8") as f:
                json.dump({"tasks": serializable_tasks}, f, indent=4)
        except Exception as e:
            self.log(f"Failed to save registry: {e}", level=logging.ERROR)

    def _schedule_in_engine(self, task: ScheduledTask):
        if task.status != "ACTIVE":
            return

        trigger = None
        if task.type == "REPEAT":
            kwargs = {task.period_unit: float(task.schedule)}
            # Special case for milliseconds as APScheduler doesn't support them directly
            if task.period_unit == "milliseconds":
                kwargs = {"seconds": float(task.schedule) / 1000.0}
            elif task.period_unit == "months":
                # Use CronTrigger for months to ensure calendar alignment
                trigger = CronTrigger(month=f"*/{int(task.schedule)}")
            
            if not trigger:
                trigger = IntervalTrigger(**kwargs)
                
        elif task.type == "CALENDAR":
            trigger = CronTrigger.from_crontab(task.schedule)
        elif task.type == "ONE_SHOT":
            run_time = datetime.now() + pd.Timedelta(**{task.period_unit: float(task.schedule)})
            trigger = DateTrigger(run_date=run_time)

        if trigger:
            self.scheduler.add_job(
                func=self._enqueue_task,
                trigger=trigger,
                args=[task.task_id],
                id=task.task_id,
                replace_existing=True,
                misfire_grace_time=3600
            )

    def _enqueue_task(self, task_id: str):
        """Called by APScheduler when a task is triggered."""
        if task_id not in self.tasks:
            return
        
        task = self.tasks[task_id]
        if task.status != "ACTIVE":
            return

        # Check repeat count
        if task.repeat_count > 0 and task.current_run_count >= task.repeat_count:
            self.log(f"Task {task.task_id} reached repeat limit ({task.repeat_count}). Completing.")
            task.status = "COMPLETED"
            self.scheduler.remove_job(task_id)
            self._save_registry()
            return

        # Add to prioritized queue
        if task_id in self.pending_tasks:
            logger.debug(f"[HEARTBEAT] Task {task_id} is already pending. Skipping enqueue.")
            return

        queue = self.queues.get(task.priority, self.queues["NORMAL"])
        if self.loop:
            self.pending_tasks.add(task_id)
            self.loop.call_soon_threadsafe(queue.put_nowait, task_id)
        else:
            logger.error("[HEARTBEAT] No event loop captured. Cannot enqueue task.")
        logger.debug(f"[HEARTBEAT] Enqueued {task.priority} task: {task_id}")

    async def _execution_worker(self):
        """Sequential prioritizer loop with anti-starvation."""
        self.log("Heartbeat Execution Worker Online.")
        starvation_counter = 0
        
        while self._is_running:
            try:
                task_to_run = None
                
                # [ANTI-STARVATION] Every 5 consecutive high-priority executions, give lower tiers a chance
                if starvation_counter >= 5:
                    for p in ["LOW", "BACKGROUND"]:
                        q = self.queues[p]
                        if not q.empty() and (p != "BACKGROUND" or self.platform_idle):
                            task_id = await q.get()
                            if task_id in self.pending_tasks:
                                self.pending_tasks.remove(task_id)
                            task_to_run = self.tasks.get(task_id)
                            if task_to_run:
                                break
                    starvation_counter = 0

                if not task_to_run:
                    # Check queues in priority order
                    for p in ["CRITICAL", "HIGH", "NORMAL", "LOW"]:
                        q = self.queues[p]
                        if not q.empty():
                            task_id = await q.get()
                            if task_id in self.pending_tasks:
                                self.pending_tasks.remove(task_id)
                            task_to_run = self.tasks.get(task_id)
                            if task_to_run:
                                break
                    
                    # Background tasks only if idle and no other tasks pending
                    if not task_to_run and self.platform_idle:
                        bq = self.queues["BACKGROUND"]
                        if not bq.empty():
                            task_id = await bq.get()
                            if task_id in self.pending_tasks:
                                self.pending_tasks.remove(task_id)
                            task_to_run = self.tasks.get(task_id)

                if task_to_run:
                    if task_to_run.priority in ["CRITICAL", "HIGH", "NORMAL"]:
                        starvation_counter += 1
                    else:
                        starvation_counter = 0
                        
                    await self._execute_task(task_to_run)
                else:
                    starvation_counter = 0
                    await asyncio.sleep(0.5) # Heartbeat tic
                    
            except Exception as e:
                self.log(f"Worker Error: {e}", level=logging.ERROR)
                await asyncio.sleep(1)

    async def _execute_task(self, task: ScheduledTask):
        should_log = True
        if task.type == "REPEAT":
            try:
                if task.period_unit == "milliseconds":
                    should_log = False
                elif task.period_unit == "seconds" and float(task.schedule) < 3600:
                    should_log = False
                elif task.period_unit == "minutes" and float(task.schedule) < 60:
                    should_log = False
            except ValueError:
                pass

        if should_log:
            self.log(f"[EXEC] {task.priority} Task: {task.name} ({task.task_id})")
        
        async def _run_task():
            task.start_time = time.time()
            self.executing_tasks[task.task_id] = task
            
            try:
                if task.callback:
                    # Internal Callback
                    if asyncio.iscoroutinefunction(task.callback):
                        await task.callback()
                    else:
                        task.callback()
                    # If we got here, callback succeeded
                    task.last_run = datetime.now().isoformat()
                    task.current_run_count += 1
                elif task.command:
                    # External Command
                    process = await asyncio.create_subprocess_shell(
                        task.command,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    stdout, stderr = await process.communicate()
                    if process.returncode == 0:
                        if should_log:
                            self.log(f"Status: COMPLETED {task.task_id}")
                        task.last_run = datetime.now().isoformat()
                        task.current_run_count += 1
                        self._save_registry()
                    else:
                        self.log(f"Status: FAILED {task.task_id}: {stderr.decode()}", level=logging.ERROR)
                    
            except Exception as e:
                self.log(f" Runtime Error for {task.task_id}: {e}", level=logging.ERROR)
            finally:
                task.start_time = None
                if task.task_id in self.executing_tasks:
                    del self.executing_tasks[task.task_id]
                    
        # Dispatch the task to the event loop so the scheduler worker isn't blocked
        asyncio.create_task(_run_task())

    # --- Helper Functions API ---

    def add_timer(self, task_id, name, type, schedule, period_unit=None, repeat_count=0, priority="NORMAL", command=None, callback=None):
        task = ScheduledTask(
            task_id=task_id,
            name=name,
            type=type,
            priority=priority,
            schedule=schedule,
            period_unit=period_unit,
            repeat_count=repeat_count,
            command=command,
            callback=callback
        )
        self.tasks[task_id] = task
        self._schedule_in_engine(task)
        self.log(f" Registered {type}: {name} ({task_id}) [Priority: {priority}]")
        if command:
            self._save_registry()

    def remove_timer(self, task_id):
        if task_id in self.tasks:
            if self.scheduler.get_job(task_id):
                self.scheduler.remove_job(task_id)
            del self.tasks[task_id]
            self.log(f"REMOVED: {task_id}")
            self._save_registry()

    def adjust_priority(self, task_id, priority):
        if task_id in self.tasks:
            self.tasks[task_id].priority = priority
            self.log(f" Adjusted priority for {task_id} to {priority}")
            self._save_registry()

    def query_active_timers(self) -> List[Dict[str, Any]]:
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "status": t.status,
                "priority": t.priority,
                "next_run": str(self.scheduler.get_job(t.task_id).next_run_time) if self.scheduler.get_job(t.task_id) else None
            }
            for t in self.tasks.values()
        ]

    def query_executing_tasks(self) -> List[Dict[str, Any]]:
        now = time.time()
        return [
            {
                "task_id": t.task_id,
                "name": t.name,
                "running_time": f"{now - t.start_time:.2f}s" if t.start_time else "0s"
            }
            for t in self.executing_tasks.values()
        ]

    def get_execution_log(self, limit=100) -> List[str]:
        if not os.path.exists(self.log_file):
            return []
        with open(self.log_file, "r", encoding="utf-8") as f:
            lines = f.readlines()
            return [l.strip() for l in lines[-limit:]]

    def promote_task(self, task_id):
        """Forces immediate execution by jumping to CRITICAL queue."""
        if task_id in self.tasks:
            self.log(f"PROMOTING: {task_id} to CRITICAL queue.")
            if self.loop:
                self.pending_tasks.add(task_id)
                self.loop.call_soon_threadsafe(self.queues["CRITICAL"].put_nowait, task_id)

    def reconcile_daily_tasks(self) -> str:
        """
        Manually triggers a check for all daily/periodic tasks.
        Enqueues any missed tasks into the HIGH priority queue.
        """
        self.log("EVENT: Manual Daily Reconciliation Initiated.")
        found_missed = []
        already_pending = []
        up_to_date = []
        
        now = datetime.now()
        today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)

        for task_id, task in self.tasks.items():
            if task.status != "ACTIVE":
                continue
                
            # Define "Daily" as CALENDAR tasks or REPEAT tasks with >= 12h periods
            is_daily = False
            if task.type == "CALENDAR":
                is_daily = True
            elif task.type == "REPEAT":
                if task.period_unit == "hours" and float(task.schedule) >= 12:
                    is_daily = True
                elif task.period_unit in ["days", "weeks", "months"]:
                    is_daily = True

            if not is_daily:
                continue

            # Check if it has run today
            has_run_today = False
            if task.last_run:
                try:
                    last_run_dt = datetime.fromisoformat(task.last_run)
                    if last_run_dt >= today_start:
                        has_run_today = True
                except:
                    pass
            
            if has_run_today:
                up_to_date.append(task_id)
                continue

            # Check if already in queue or running
            if task_id in self.pending_tasks or task_id in self.executing_tasks:
                already_pending.append(task_id)
                continue

            # It's a daily task, it hasn't run today, and it's not pending.
            # We treat this as a misfire/miss and promote to HIGH.
            found_missed.append(task_id)
            if self.loop:
                self.pending_tasks.add(task_id)
                self.loop.call_soon_threadsafe(self.queues["HIGH"].put_nowait, task_id)
        
        summary = f"Reconciliation Complete. Missed: {len(found_missed)}, Pending: {len(already_pending)}, OK: {len(up_to_date)}."
        if found_missed:
            summary += f" Triggered catch-up for: {', '.join(found_missed)}"
        self.log(summary)
        return summary

    def start(self):
        if self._is_running:
            return
        
        try:
            self.loop = asyncio.get_running_loop()
        except RuntimeError:
            logger.error("[HEARTBEAT] Scheduler started outside of event loop.")
        
        self._is_running = True
        self.load_from_json()
        self.scheduler.start()
        
        # Start the prioritizer worker
        self._worker_task = asyncio.create_task(self._execution_worker())
        self.log("EVENT: Heartbeat Engine ONLINE.")
        
        # Check misfires for all scheduled tasks after boot
        for t in self.tasks.values():
            self._evaluate_misfire(t)

    def stop(self):
        self._is_running = False
        self.scheduler.shutdown()
        if self._worker_task:
            self._worker_task.cancel()
        self.log("EVENT: Heartbeat Engine OFFLINE.")

    def _evaluate_misfire(self, task: ScheduledTask):
        if not task.last_run or task.status != "ACTIVE":
            return
            
        try:
            from apscheduler.triggers.cron import CronTrigger
            from apscheduler.triggers.interval import IntervalTrigger
            from datetime import datetime, timedelta
            
            # Reconstruct trigger
            trigger = None
            if task.type == "REPEAT":
                kwargs = {task.period_unit: float(task.schedule)}
                if task.period_unit == "milliseconds":
                    kwargs = {"seconds": float(task.schedule) / 1000.0}
                elif task.period_unit == "months":
                    trigger = CronTrigger(month=f"*/{int(task.schedule)}")
                if not trigger:
                    trigger = IntervalTrigger(**kwargs)
            elif task.type == "CALENDAR":
                trigger = CronTrigger.from_crontab(task.schedule)
                
            if trigger:
                last_run_dt = datetime.fromisoformat(task.last_run)
                if last_run_dt.tzinfo is None:
                    last_run_dt = last_run_dt.replace(tzinfo=datetime.now().astimezone().tzinfo)
                next_time = trigger.get_next_fire_time(None, last_run_dt)
                
                if next_time:
                    now = datetime.now(next_time.tzinfo)
                    if next_time < now:
                        delta = now - next_time
                        time_missed_str = f"MISSED by {(delta.total_seconds() / 3600):.1f}hrs"
                        if delta <= timedelta(hours=24):
                            self.log(f" MISFIRE DETECTED for {task.task_id} ({time_missed_str}). Executing CATCH-UP inside HIGH queue.")
                            if self.loop:
                                self.loop.call_soon_threadsafe(self.queues["HIGH"].put_nowait, task.task_id)
                        else:
                            self.log(f" MISFIRE STALE for {task.task_id} ({time_missed_str}). Ignored because > 24 hours.")
        except Exception as e:
            self.log(f"Failed to evaluate misfire for {task.task_id}: {e}", level=logging.ERROR)

# Singleton Instance
cobalt_scheduler = CobaltScheduler()
