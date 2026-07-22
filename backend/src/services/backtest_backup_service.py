import os
import json
import shutil
import logging
from datetime import datetime

logger = logging.getLogger(__name__)

PROJECT_ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
PRIMARY_CACHE_PATH = os.path.join(PROJECT_ROOT, "backend", "data", "trends_cache.json")
SECONDARY_CACHE_PATH = os.path.join(PROJECT_ROOT, "data", "trends_cache.json")
ARCHIVE_DIR = os.path.join(PROJECT_ROOT, "data", "archive")

def backup_backtest_db(force=False):
    """
    Creates a daily timestamped backup of trends_cache.json (Backtest DB)
    in data/archive/ (e.g. TrendsCacheDailyBackup_2026-07-21.json)
    and maintains a 30-day backup history.
    """
    os.makedirs(ARCHIVE_DIR, exist_ok=True)
    today_str = datetime.now().strftime("%Y-%m-%d")
    backup_filename = f"TrendsCacheDailyBackup_{today_str}.json"
    backup_path = os.path.join(ARCHIVE_DIR, backup_filename)
    
    # Locate valid cache file
    src_path = PRIMARY_CACHE_PATH if os.path.exists(PRIMARY_CACHE_PATH) else SECONDARY_CACHE_PATH
    if not os.path.exists(src_path):
        logger.warning(f"Backtest Backup: Source cache {src_path} does not exist. Skipping backup.")
        return False
        
    # Check if today's backup already exists unless forced
    if os.path.exists(backup_path) and not force:
        logger.info(f"Backtest Backup: Today's backup ({backup_filename}) already exists.")
        return True
        
    try:
        shutil.copy2(src_path, backup_path)
        logger.info(f"Backtest Backup: Successfully created daily backup -> {backup_path}")
        
        # Mirror copy to data/trends_cache.json for sync consistency
        if src_path == PRIMARY_CACHE_PATH:
            os.makedirs(os.path.dirname(SECONDARY_CACHE_PATH), exist_ok=True)
            shutil.copy2(PRIMARY_CACHE_PATH, SECONDARY_CACHE_PATH)
            
        # Mirror to Google Drive G:\My Drive\Cobalt_Backups\
        try:
            from src.services.gdrive_backup_service import sync_file_to_gdrive, sync_entire_archive_to_gdrive
            sync_file_to_gdrive(backup_path, f"archive/{backup_filename}")
            sync_file_to_gdrive(src_path, "trends_cache.json")
            sync_entire_archive_to_gdrive(ARCHIVE_DIR)
        except Exception as g_err:
            logger.debug(f"Google Drive sync skipped: {g_err}")

        # Clean up backups older than 30 days
        cleanup_old_backtest_backups(days=30)
        return True
    except Exception as e:
        logger.error(f"Backtest Backup: Failed to create daily backup: {e}")
        return False

def cleanup_old_backtest_backups(days=30):
    """Retains the last N days of backtest DB backups in data/archive/."""
    try:
        if not os.path.exists(ARCHIVE_DIR): return
        files = [f for f in os.listdir(ARCHIVE_DIR) if f.startswith("TrendsCacheDailyBackup_") and f.endswith(".json")]
        if len(files) <= days: return
        
        files.sort()
        to_delete = files[:-days]
        for f in to_delete:
            full_p = os.path.join(ARCHIVE_DIR, f)
            os.remove(full_p)
            logger.info(f"Backtest Backup Cleanup: Removed expired backup {f}")
    except Exception as e:
        logger.error(f"Backtest Backup Cleanup Failed: {e}")

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    backup_backtest_db(force=True)
