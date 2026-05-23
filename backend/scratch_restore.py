import os
import sys
import shutil

sys.path.append('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/backend')
cache_path = 'C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/brokerage_cache.json'
if os.path.exists(cache_path):
    os.remove(cache_path)

from src.services.atp_importer import process_dropzone_files
res = process_dropzone_files('C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent/data/dropzone/archive')
print(res)
