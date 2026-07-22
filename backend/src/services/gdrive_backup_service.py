import os
import shutil
import logging
from typing import Optional

logger = logging.getLogger(__name__)

GDRIVE_BASE_DIR = r"G:\My Drive\Cobalt_Backups"

def is_gdrive_available() -> bool:
    """Checks if Google Drive path G:\My Drive is mounted and accessible."""
    try:
        gdrive_root = r"G:\My Drive"
        return os.path.exists(gdrive_root)
    except Exception:
        return False

def sync_file_to_gdrive(src_path: str, relative_subpath: Optional[str] = None) -> bool:
    """
    Safely mirrors a local file to G:\My Drive\Cobalt_Backups\.
    If relative_subpath is provided (e.g. 'archive/TrendsCacheDailyBackup_2026-07-21.json'),
    it will be placed in G:\My Drive\Cobalt_Backups\archive\TrendsCacheDailyBackup_2026-07-21.json.
    """
    if not is_gdrive_available():
        logger.warning(f"Google Drive Backup: G:\\My Drive is not accessible. Skipping sync for {src_path}")
        return False

    if not os.path.exists(src_path):
        logger.warning(f"Google Drive Backup: Source file {src_path} does not exist.")
        return False

    try:
        if relative_subpath:
            dest_path = os.path.join(GDRIVE_BASE_DIR, relative_subpath)
        else:
            dest_path = os.path.join(GDRIVE_BASE_DIR, os.path.basename(src_path))

        os.makedirs(os.path.dirname(dest_path), exist_ok=True)
        shutil.copy2(src_path, dest_path)
        logger.info(f"[GDRIVE_SYNC] Successfully mirrored {os.path.basename(src_path)} -> {dest_path}")
        return True
    except Exception as e:
        logger.error(f"[GDRIVE_SYNC] Failed to mirror {src_path} to Google Drive: {e}")
        return False

def sync_entire_archive_to_gdrive(archive_dir: str) -> int:
    """
    Mirrors all files in data/archive (including subfolders) to G:\My Drive\Cobalt_Backups\archive\.
    """
    if not is_gdrive_available() or not os.path.exists(archive_dir):
        return 0

    count = 0
    gdrive_archive_dir = os.path.join(GDRIVE_BASE_DIR, "archive")
    try:
        for root, dirs, files in os.walk(archive_dir):
            for file in files:
                # Skip temporary download or hidden lock files
                if file.startswith(".") or file.endswith(".tmp"):
                    continue
                full_src = os.path.join(root, file)
                rel_p = os.path.relpath(full_src, archive_dir)
                dest_p = os.path.join(gdrive_archive_dir, rel_p)
                
                os.makedirs(os.path.dirname(dest_p), exist_ok=True)
                
                # Copy if destination doesn't exist or source is newer
                if not os.path.exists(dest_p) or os.path.getmtime(full_src) > os.path.getmtime(dest_p):
                    shutil.copy2(full_src, dest_p)
                    count += 1
        if count > 0:
            logger.info(f"[GDRIVE_SYNC] Mirrored {count} archive file(s) to {gdrive_archive_dir}")
        return count
    except Exception as e:
        logger.error(f"[GDRIVE_SYNC] Archive mirror error: {e}")
        return count

if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    print("Google Drive Available:", is_gdrive_available())
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "..", ".."))
    local_archive = os.path.join(project_root, "data", "archive")
    synced = sync_entire_archive_to_gdrive(local_archive)
    print(f"Synced {synced} file(s) to G:\\My Drive\\Cobalt_Backups\\archive")
