from langchain_core.tools import tool
from typing import Optional, List, Dict, Any
from src.services.scheduler import cobalt_scheduler
import logging

logger = logging.getLogger(__name__)

@tool
def manage_scheduled_tasks(
    action: str, # REGISTER, PAUSE, RESUME, DELETE, PROMOTE, QUERY, LOG, EXECUTING, ADJUST, RECONCILE
    task_id: str,
    name: Optional[str] = None,
    task_type: Optional[str] = None, # REPEAT, ONE_SHOT, CALENDAR
    priority: str = "NORMAL", # CRITICAL, HIGH, NORMAL, LOW, BACKGROUND
    schedule: Optional[str] = None,
    period_unit: Optional[str] = None, # milliseconds, seconds, minutes, hours, days, weeks, months
    repeat_count: int = 0,
    command: Optional[str] = None
) -> str:
    """
    Manages the Cobalt Heartbeat Scheduler. Allows for registering, modifying, 
    and monitoring rhythmic platform tasks.
    
    Args:
        action: The operation to perform (REGISTER, PAUSE, RESUME, DELETE, PROMOTE, QUERY, LOG, EXECUTING, ADJUST, RECONCILE).
        task_id: Unique identifier for the task.
        name: Human-readable name (required for REGISTER).
        task_type: Type of timing (REPEAT, ONE_SHOT, CALENDAR).
        priority: Priority tier (CRITICAL, HIGH, NORMAL, LOW, BACKGROUND).
        schedule: Timing value (unit count for REPEAT/ONE_SHOT, or calendar string for CALENDAR).
        period_unit: Time unit for REPEAT/ONE_SHOT.
        repeat_count: Number of times to repeat (0 for indefinite).
        command: Shell or Python command to execute (external tasks).
    """
    action = action.upper()
    priority = priority.upper()
    
    try:
        if action == "REGISTER":
            if not name or not task_type or not schedule:
                return "Error: name, task_type, and schedule are required for REGISTER."
            
            cobalt_scheduler.add_timer(
                task_id=task_id,
                name=name,
                type=task_type.upper(),
                schedule=schedule,
                period_unit=period_unit.lower() if period_unit else None,
                repeat_count=repeat_count,
                priority=priority,
                command=command
            )
            return f"Successfully registered task: {name} ({task_id}) as {task_type} with {priority} priority."

        elif action == "DELETE":
            cobalt_scheduler.remove_timer(task_id)
            return f"Successfully removed task: {task_id}"

        elif action == "PAUSE":
            if task_id in cobalt_scheduler.tasks:
                cobalt_scheduler.tasks[task_id].status = "PAUSED"
                if cobalt_scheduler.scheduler.get_job(task_id):
                    cobalt_scheduler.scheduler.pause_job(task_id)
                cobalt_scheduler._save_registry()
                return f"Task {task_id} has been PAUSED."
            return f"Error: Task {task_id} not found."

        elif action == "RESUME":
            if task_id in cobalt_scheduler.tasks:
                cobalt_scheduler.tasks[task_id].status = "ACTIVE"
                if cobalt_scheduler.scheduler.get_job(task_id):
                    cobalt_scheduler.scheduler.resume_job(task_id)
                cobalt_scheduler._save_registry()
                return f"Task {task_id} has been RESUMED."
            return f"Error: Task {task_id} not found."

        elif action == "PROMOTE":
            cobalt_scheduler.promote_task(task_id)
            return f"Task {task_id} has been promoted to CRITICAL queue for immediate execution."

        elif action == "ADJUST":
            cobalt_scheduler.adjust_priority(task_id, priority)
            return f"Priority for {task_id} adjusted to {priority}."

        elif action == "QUERY":
            timers = cobalt_scheduler.query_active_timers()
            if not timers:
                return "No active timers found."
            
            output = ["### Active Timers"]
            for t in timers:
                output.append(f"- **{t['name']}** ({t['task_id']}): Status={t['status']}, Priority={t['priority']}, Next Run={t['next_run']}")
            return "\n".join(output)

        elif action == "EXECUTING":
            executing = cobalt_scheduler.query_executing_tasks()
            if not executing:
                return "No tasks currently executing."
            
            output = ["### Currently Executing Tasks"]
            for t in executing:
                output.append(f"- **{t['name']}** ({t['task_id']}): Running for {t['running_time']}")
            return "\n".join(output)

        elif action == "LOG":
            logs = cobalt_scheduler.get_execution_log(20)
            if not logs:
                return "No execution logs found."
            return "### Execution Log (Last 20 entries)\n" + "\n".join([f"- {l}" for l in logs])

        elif action == "RECONCILE":
            return cobalt_scheduler.reconcile_daily_tasks()

        else:
            return f"Error: Unknown action '{action}'."

    except Exception as e:
        logger.error(f"Error in manage_scheduled_tasks: {e}")
        return f"Error managing tasks: {str(e)}"
