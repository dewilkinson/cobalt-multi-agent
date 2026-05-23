import os

file_path = r"C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend\src\server\app.py"
with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
    for i, line in enumerate(f, 1):
        if "TV_SYNC" in line:
            print(f"{i}: {line.strip()}")
        if "synchronization complete" in line.lower():
            print(f"{i}: {line.strip()}")
