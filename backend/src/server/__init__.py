import sys
import os

# Emergency BSON patch for local environment
try:
    from bson import ObjectId
except (ImportError, AttributeError):
    try:
        import pymongo.bson as pymongo_bson
        sys.modules['bson'] = pymongo_bson
        from bson import ObjectId
        # patch_logger = __import__("logging").getLogger("bson_patch")
        # patch_logger.info("Successfully monkey-patched BSON in server package")
    except Exception:
        pass

from .app import app

__all__ = ["app"]
