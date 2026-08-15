import os
import json
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PRIMARY_CACHE_PATH = os.path.join(PROJECT_ROOT, "backend", "data", "trends_cache.json")
EXEC_HISTORY_PATH  = os.path.join(PROJECT_ROOT, "data", "strategy_execution_history.json")
STRATEGY_LOGS_DIR  = os.path.join(PROJECT_ROOT, "strategies", "DSV", "logs")
ARCHIVE_DIR        = os.path.join(PROJECT_ROOT, "data", "archive")

def backup_backtest_db(force=False):
    """
    Creates daily timestamped backups of:
      1. trends_cache.json (Backtest DB)
      2. strategy_execution_history.json (Strategy Run History)
      3. Symbol Strategy Logs (strategies/DSV/logs/)
    in data/archive/ and mirrors to Google Drive.
    """
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    
    # 1. Back up trends_cache.json
    backup_filename = f"TrendsCacheDailyBackup_{today_str}.json"
    backup_path = os.path.join(ARCHIVE_DIR, backup_filename)
    if os.path.exists(PRIMARY_CACHE_PATH):
        if not os.path.exists(backup_path) or force:
            shutil.copy2(PRIMARY_CACHE_PATH, backup_path)
            logger.info(f"Backtest Backup: Created trends_cache backup -> {backup_path}")

    # 2. Back up strategy_execution_history.json
    hist_backup_name = f"StrategyExecutionHistoryDailyBackup_{today_str}.json"
    hist_backup_path = os.path.join(ARCHIVE_DIR, hist_backup_name)
    if os.path.exists(EXEC_HISTORY_PATH):
        if not os.path.exists(hist_backup_path) or force:
            shutil.copy2(EXEC_HISTORY_PATH, hist_backup_path)
            logger.info(f"Strategy History Backup: Created history backup -> {hist_backup_path}")

    # 3. Back up Symbol Strategy Logs (strategies/DSV/logs/)
    logs_backup_zip = os.path.join(ARCHIVE_DIR, f"StrategySymbolLogsDailyBackup_{today_str}")
    if os.path.exists(STRATEGY_LOGS_DIR):
        try:
            shutil.make_archive(logs_backup_zip, 'zip', STRATEGY_LOGS_DIR)
            logger.info(f"Symbol Logs Backup: Created ZIP archive -> {logs_backup_zip}.zip")
        except Exception as log_err:
            logger.error(f"Symbol Logs Backup Error: {log_err}")

    # 4. Mirror to Google Drive G:\My Drive\Cobalt_Backups\
    try:
        from src.services.gdrive_backup_service import sync_file_to_gdrive, sync_entire_archive_to_gdrive
        if os.path.exists(backup_path):
            sync_file_to_gdrive(backup_path, f"archive/{backup_filename}")
        if os.path.exists(hist_backup_path):
            sync_file_to_gdrive(hist_backup_path, f"archive/{hist_backup_name}")
        if os.path.exists(f"{logs_backup_zip}.zip"):
            sync_file_to_gdrive(f"{logs_backup_zip}.zip", f"archive/StrategySymbolLogsDailyBackup_{today_str}.zip")
        
        # Mirror raw symbol markdown files directly to GDrive strategy_logs/ folder
        if os.path.exists(STRATEGY_LOGS_DIR):
            for log_f in os.listdir(STRATEGY_LOGS_DIR):
                if log_f.endswith(".md"):
                    sync_file_to_gdrive(os.path.join(STRATEGY_LOGS_DIR, log_f), f"strategy_logs/{log_f}")

        sync_entire_archive_to_gdrive(ARCHIVE_DIR)
    except Exception as g_err:
        logger.debug(f"Google Drive sync skipped: {g_err}")

    cleanup_old_backtest_backups(days=30)
    return True

def cleanup_old_backtest_backups(days=30):
    """Retains the last N days of backtest backups in data/archive/."""
    try:
        if not os.path.exists(ARCHIVE_DIR): return
        files = [f for f in os.listdir(ARCHIVE_DIR) if ("DailyBackup_" in f)]
        if len(files) <= (days * 3): return
        
        files.sort()
        to_delete = files[:-(days * 3)]
        for f in to_delete:
            full_p = os.path.join(ARCHIVE_DIR, f)
            if os.path.isfile(full_p):
                os.remove(full_p)
                logger.info(f"Backtest Backup Cleanup: Removed expired backup {f}")
    except Exception as e:
        logger.error(f"Backtest Backup Cleanup Failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backup_backtest_db(force=True)
