import os

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"

# Pair of (old_path_lower, new_path)
replacements = [
    ("C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent", "C:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"),
    ("C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent", "C:\\Users\\rende\\.gemini\\antigravity\\worktrees\\cobalt-multi-agent"),
    ("c:\\\\github\\\\cobalt-multi-agent", "C:\\\\Users\\\\rende\\\\.gemini\\\\antigravity\\\\worktrees\\\\cobalt-multi-agent")
]

exclude_dirs = {".git", "node_modules", ".next", ".pytest_cache", "__pycache__"}

def replace_paths():
    count = 0
    for root, dirs, files in os.walk(workspace_dir):
        # Exclude directories in-place
        dirs[:] = [d for d in dirs if d not in exclude_dirs]
        
        for file in files:
            file_path = os.path.join(root, file)
            # Skip binary files by extension
            if file.endswith(('.png', '.jpg', '.jpeg', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz')):
                continue
                
            try:
                with open(file_path, 'r', encoding='utf-8', errors='ignore') as f:
                    content = f.read()
            except Exception as e:
                continue
                
            has_changes = False
            for old_p, new_p in replacements:
                # Find and replace all occurrences (case-insensitive search)
                idx = 0
                while True:
                    idx = content.lower().find(old_p, idx)
                    if idx == -1:
                        break
                    # Replace with the new path
                    content = content[:idx] + new_p + content[idx + len(old_p):]
                    idx += len(new_p)
                    has_changes = True
                    
            if has_changes:
                try:
                    with open(file_path, 'w', encoding='utf-8') as f:
                        f.write(content)
                    print(f"Replaced paths in {file_path}")
                    count += 1
                except Exception as e:
                    print(f"Failed to write {file_path}: {e}")
                    
    print(f"Replacement complete! Updated {count} files.")

if __name__ == "__main__":
    replace_paths()
