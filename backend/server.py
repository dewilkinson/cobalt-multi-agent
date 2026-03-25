# Copyright (c) 2025 Bytedance Ltd. and/or its affiliates
# SPDX-License-Identifier: MIT

"""
Server script for running the Cobalt Multiagent API.
"""
import sys
import os

# 1. FINAL BSON MONKEY-PATCH: Namespace Stitching
try:
    import bson
    from bson import ObjectId
except (ImportError, AttributeError):
    try:
        # Patch the base bson module
        import pymongo.bson as pymongo_bson
        sys.modules['bson'] = pymongo_bson
        
        # Manually stitch ObjectId if missing
        from bson.objectid import ObjectId
        setattr(sys.modules['bson'], 'ObjectId', ObjectId)
        
        print(f"Successfully stitched BSON ObjectId into sys.modules: {ObjectId}")
    except Exception as e:
        print(f"Failed to stitch BSON: {str(e)}")
        pass

import asyncio
import argparse
import logging
import signal
import uvicorn

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)

logger = logging.getLogger(__name__)

# To ensure compatibility with Windows event loop issues when using Uvicorn and Asyncio Checkpointer,
# This is necessary because some libraries expect a selector-based event loop.
# This is a workaround for issues with Uvicorn and Watchdog on Windows.
# See:
# Since Python 3.8 the default on Windows is the Proactor event loop,
# which lacks add_reader/add_writer and can break libraries that expect selector-based I/O (e.g., some Uvicorn/Watchdog/stdio integrations).
# For compatibility, this forces the selector loop.
if os.name == "nt":
    logger.info("Setting Windows event loop policy for asyncio")
    asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())


def handle_shutdown(signum, frame):
    """Handle graceful shutdown on SIGTERM/SIGINT"""
    logger.info("Received shutdown signal. Starting graceful shutdown...")
    sys.exit(0)


# Register signal handlers
signal.signal(signal.SIGTERM, handle_shutdown)
signal.signal(signal.SIGINT, handle_shutdown)

if __name__ == "__main__":
    # Add current directory to sys.path for local module resolution
    current_dir = os.path.dirname(os.path.abspath(__file__))
    if current_dir not in sys.path:
        sys.path.append(current_dir)
        
    # Parse command line arguments
    parser = argparse.ArgumentParser(description="Run the Cobalt Multiagent API server")
    parser.add_argument(
        "--reload",
        action="store_true",
        help="Enable auto-reload (Note: Reload will NOT use the direct app object)",
    )
    parser.add_argument(
        "--host",
        type=str,
        default="localhost",
        help="Host to bind the server to (default: localhost)",
    )
    parser.add_argument(
        "--port",
        type=int,
        default=8000,
        help="Port to bind the server to (default: 8000)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="info",
        choices=["debug", "info", "warning", "error", "critical"],
        help="Log level (default: info)",
    )

    args = parser.parse_args()

    # Determine reload setting
    # CRITICAL: We avoid "reload=True" on Windows to keep our monkey-patch in memory.
    reload = False
    
    try:
        # 2. DIRECT IMPORT OF APP OBJECT WITHIN THE PATCHED CONTEXT
        # This will now succeed because BSON has ObjectId.
        from src.server.app import app
        
        logger.info(f"Starting Cobalt Multiagent API server on {args.host}:{args.port}")
        
        # 3. USE DIRECT APP OBJECT INSTEAD OF STRING: No more context-less re-imports
        uvicorn.run(
            app,
            host=args.host,
            port=args.port,
            reload=reload,
            log_level=args.log_level,
        )
    except Exception as e:
        logger.error(f"Failed to start server: {str(e)}")
        import traceback
        traceback.print_exc()
        sys.exit(1)
