import os
from datetime import datetime

archive_dir = "data/dropzone/archive"
if not os.path.exists(archive_dir):
    print("Archive directory not found!")
    exit(1)

for file in os.listdir(archive_dir):
    path = os.path.join(archive_dir, file)
    mtime = os.path.getmtime(path)
    dt = datetime.fromtimestamp(mtime)
    print(f"{file} | Modified: {dt} | Size: {os.path.getsize(path)} bytes")
