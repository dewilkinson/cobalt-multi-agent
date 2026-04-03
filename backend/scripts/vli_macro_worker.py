# Cobalt Multiagent - Standalone VLI Macro Worker
# Copyright (c) 2026 Dave Wilkinson <dwilkins@bluesec.ai>

import asyncio
import json
import os
import sys
import logging
from datetime import datetime
from pathlib import Path

# Add backend to path for internal imports
sys.path.append(os.path.join(os.getcwd(), "backend"))

from src.services.macro_registry import macro_registry
from src.tools.scraper import get_macro_prices
from src.config.vli import get_vli_path

# Configuration
SNAPSHOT_FILE = get_vli_path("vli_macro_snapshot.json")
REFRESH_INTERVAL = 60 # Seconds

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("VLI-Macro-Worker")

async def run_worker():
    logger.info("🚀 VLI Standalone Macro Worker Initialized.")
    logger.info(f"Target Snapshot: {SNAPSHOT_FILE}")
    
    os.makedirs(os.path.dirname(SNAPSHOT_FILE), exist_ok=True)

    while True:
        try:
            # [V10.4] Heartbeat Check: Should we be scraping?
            config_enabled = True
            try:
                with open(SNAPSHOT_FILE.replace("vli_macro_snapshot.json", "vli_session_config.json"), "r") as f:
                    config = json.load(f)
                    config_enabled = config.get("macro_enabled", True)
            except: pass
            
            if not config_enabled:
                logger.info("VLI Session: Macro scraping disabled. Shutting down worker process to conserve institutional resources.")
                sys.exit(0)

            symbols = list(macro_registry.get_macros().keys())
            logger.info(f"Synchronizing {len(symbols)} institutional benchmarks...")
            
            # Fetch all symbols in a high-efficiency batch
            data = await get_macro_prices(symbols)
            
            if data:
                snapshot = {
                    "last_updated": datetime.now().strftime("%H:%M:%S"),
                    "macros": data
                }
                
                with open(SNAPSHOT_FILE, "w", encoding="utf-8") as f:
                    json.dump(snapshot, f, indent=4)
                    
                logger.info(f"Successfully updated snapshot with {len(data)} symbols.")
            else:
                logger.warning("Scraper returned empty data. Snapshot not updated.")
                
        except Exception as e:
            logger.error(f"Worker Error: {e}")
            
        logger.info(f"Waiting {REFRESH_INTERVAL}s for next cycle...")
        await asyncio.sleep(REFRESH_INTERVAL)

if __name__ == "__main__":
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker stopped by user.")
