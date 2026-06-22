import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"

md_paths = [
    "c:/github/obsidian-vault/Journals/Daily_Trading_Report_2026-06-10.md",
    "c:/github/obsidian-vault/Journals/Daily Reports/Daily_PostMortem_2026-06-10.md",
    os.path.join(workspace_dir, "data", "reports", "performance", "Daily_PostMortem_2026-06-10.md")
]

for path in md_paths:
    if os.path.exists(path):
        with open(path, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = content.replace("$100,541.12 (Based on Single-Day PNL)", "$87,731.34 (Actual Cash Balance)")
        content = content.replace("$100,541.12", "$87,731.34")
        
        with open(path, 'w', encoding='utf-8') as f:
            f.write(content)
        print(f"Fixed: {path}")
