import os

root_dir = r"C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend"
for root, dirs, files in os.walk(root_dir):
    if ".venv" in root: continue
    for file in files:
        if file.endswith((".py", ".md", ".html", ".js")):
            file_path = os.path.join(root, file)
            try:
                with open(file_path, "r", encoding="utf-8", errors="ignore") as f:
                    for i, line in enumerate(f, 1):
                        if "" in line and "TV_SYNC" in line:
                            print(f"{file_path}:{i}: {line.strip()}")
            except:
                pass
