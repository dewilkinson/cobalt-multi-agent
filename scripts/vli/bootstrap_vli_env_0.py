import os
import sys
import subprocess
import logging

# Configure logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger("vli_bootstrap")

def run_command(command, cwd=None):
    """Run a shell command and return its output."""
    logger.info(f"Executing: {' '.join(command)}")
    try:
        result = subprocess.run(command, cwd=cwd, capture_output=True, text=True, check=True)
        return result.stdout
    except subprocess.CalledProcessError as e:
        logger.error(f"Command failed: {e.stderr}")
        return None

def main():
    logger.info("=== Cobalt Multiagent: VLI Environment Bootstrapping ===")
    
    # 1. Ensure we are in the correct directory
    script_dir = os.path.dirname(os.path.abspath(__file__))
    backend_dir = os.path.abspath(os.path.join(script_dir, ".."))
    os.chdir(backend_dir)
    logger.info(f"Working directory set to: {backend_dir}")

    # 2. Install missing dependencies (Pillow)
    logger.info("Step 1: Installing missing dependencies (Pillow)...")
    pip_install = [sys.executable, "-m", "pip", "install", "Pillow>=10.3.0"]
    if run_command(pip_install) is not None:
        logger.info("[SUCCESS] Pillow installed successfully.")
    else:
        logger.error("[FAILURE] Failed to install Pillow.")
        sys.exit(1)

    # 3. Initialize Database Schema
    logger.info("Step 2: Synchronizing Database Schema...")
    sys.path.append(backend_dir)
    try:
        from src.config.database import init_database, create_tables
        if init_database():
            logger.info("[SUCCESS] Database schema initialized.")
        else:
            logger.warning("[WARNING] Database initialization returned False, attempting direct table creation.")
            create_tables()
            logger.info("[SUCCESS] Forced table creation complete.")
    except Exception as e:
        logger.error(f"[FAILURE] Error during database sync: {e}")
        sys.exit(1)

    # 4. Verification Check
    logger.info("Step 3: Verifying Schema Integrity...")
    try:
        from src.config.database import get_session_local, PersistentCache
        SessionLocal = get_session_local()
        with SessionLocal() as db:
            # Simple query to check if table exists
            count = db.query(PersistentCache).count()
            logger.info(f"[SUCCESS] Schema verification passed. PersistentCache table active (Records: {count}).")
    except Exception as e:
        logger.error(f"[FAILURE] Schema verification failed: {e}")
        sys.exit(1)

    # 5. Cleanup Orphans
    logger.info("Step 4: Cleaning up orphan database files...")
    root_dir = os.path.abspath(os.path.join(backend_dir, ".."))
    orphans = [
        os.path.join(root_dir, "vli_test.db"),
        os.path.join(backend_dir, "vli_test.db")
    ]
    for orphan in orphans:
        if os.path.exists(orphan):
            try:
                os.remove(orphan)
                logger.info(f"[SUCCESS] Removed orphan: {orphan}")
            except Exception as e:
                logger.warning(f"[WARNING] Could not remove orphan {orphan}: {e}")

    logger.info("=== VLI Environment Bootstrapped Successfully ===")

if __name__ == "__main__":
    main()
