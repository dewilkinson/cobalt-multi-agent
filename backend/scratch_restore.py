import os
import sys
import shutil

sys.path.append('c:/github/cobalt-multi-agent/backend')
cache_path = 'c:/github/cobalt-multi-agent/data/brokerage_cache.json'
if os.path.exists(cache_path):
    os.remove(cache_path)

from src.services.atp_importer import process_dropzone_files
res = process_dropzone_files('c:/github/cobalt-multi-agent/data/dropzone/archive')
print(res)
