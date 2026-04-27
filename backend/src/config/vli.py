# Cobalt Multiagent - VLI Configuration
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>

import os

# --- Vault Mount Points ---
VAULT_ROOT = os.environ.get("OBSIDIAN_VAULT_PATH", r"C:\github\obsidian-vault")
COBALT_DIR = "_cobalt"
INBOX_DIR = "inbox"
ARCHIVE_DIR = "archives"
JOURNALS_DIR = "CMA journals"
ACTION_PLAN_ARCHIVE_DIR = "archives/action_plans"
GUI_VIBE_FILE = "gui_vibe.json"
PREFERRED_EDITOR = os.environ.get("VLI_PREFERRED_EDITOR", "notepad.exe")

# --- Filenames ---
ACTION_PLAN_DIR = "action_plans"
SPECIALIZATION_FILE = "Vision_Analyst_Specialization.md"
SCHEDULER_JSON = "06_Resources/Scheduler/scheduler.json"
SCHEDULER_LOG = "04_Archive/Logs/Scheduler.log"


def get_vli_path(subpath: str = "") -> str:
    """Get the full path to a Cobalt-related file or directory."""
    base = os.path.abspath(os.path.join(VAULT_ROOT, COBALT_DIR))
    if subpath:
        return os.path.abspath(os.path.join(base, subpath))
    return base

def purge_stale_vli_sessions():
    """Removes dynamic telemetry files older than 24 hours to prevent Vault bloat."""
    import time
    base = os.path.abspath(os.path.join(VAULT_ROOT, COBALT_DIR))
    if not os.path.exists(base):
        return
        
    cutoff_time = time.time() - (24 * 3600)
    for filename in os.listdir(base):
        if filename.startswith("VLI_Raw_Telemetry_") and filename.endswith(".md"):
            filepath = os.path.join(base, filename)
            try:
                if os.path.getmtime(filepath) < cutoff_time:
                    os.remove(filepath)
            except Exception:
                pass



def get_action_plan_path() -> str:
    from datetime import datetime

    today = datetime.now().strftime("%Y-%m-%d")
    filename = f"{today} Action Plan.md"
    return os.path.join(get_vli_path(ACTION_PLAN_DIR), filename)


def get_inbox_path() -> str:
    return get_vli_path(INBOX_DIR)


def get_archive_path() -> str:
    return get_vli_path(ARCHIVE_DIR)


def get_gui_vibe_path() -> str:
    """Get the full path to the persistent GUI vibe settings."""
    return get_vli_path(GUI_VIBE_FILE)


def get_journals_path() -> str:
    """Get the full path to the journals folder."""
    return os.path.join(VAULT_ROOT, JOURNALS_DIR)


def get_action_plan_archive_path() -> str:
    """Get the full path to the action plan archive."""
    return get_vli_path(ACTION_PLAN_ARCHIVE_DIR)


def get_scheduler_json_path() -> str:
    """Get the full path to the scheduler registry."""
    return os.path.join(VAULT_ROOT, SCHEDULER_JSON)


def get_scheduler_log_path() -> str:
    """Get the full path to the scheduler audit log."""
    return os.path.join(VAULT_ROOT, SCHEDULER_LOG)


# --- Singleton Rule Engine ---
from src.services.inbox_rules import InboxRuleEngine

inbox_rule_engine = InboxRuleEngine(VAULT_ROOT)
