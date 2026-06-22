import os
from datetime import datetime

base_dir = "C:/Users/rende"
exclude_dirs = {
    "AppData", ".gemini", ".cache", ".pyenv", ".local", 
    ".antigravity-ide", ".antigravity", ".vscode", ".vscode-shared",
    "node_modules", "Application Data", "Local Settings"
}

print("Searching for files modified since May 15, 2026...")
found = []

for root, dirs, files in os.walk(base_dir):
    # Filter out excluded directories
    dirs[:] = [d for d in dirs if d not in exclude_dirs and not d.startswith('.')]
    
    # Limit depth to 4
    depth = root[len(base_dir):].count(os.sep)
    if depth > 4:
        dirs[:] = []  # stop walking deeper
        continue
        
    for file in files:
        if file.lower().endswith(('.csv', '.html', '.txt')):
            path = os.path.join(root, file)
            try:
                mtime = os.path.getmtime(path)
                dt = datetime.fromtimestamp(mtime)
                if dt.year == 2026 and dt.month == 5 and (15 <= dt.day <= 23):
                    print(f"Found: {path} | Modified: {dt} | Size: {os.path.getsize(path)} bytes")
                    found.append(path)
            except Exception:
                pass

print(f"Finished search. Found {len(found)} files.")
