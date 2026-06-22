import subprocess
import os
import re

workspace_dir = "c:/Users/rende/.gemini/antigravity/worktrees/cobalt-multi-agent"

def run_git_status():
    res = subprocess.run(["git", "status", "--porcelain"], cwd=workspace_dir, capture_output=True, text=True)
    return res.stdout.splitlines()

def main():
    lines = run_git_status()
    
    # 1. Gather all files mentioned in git status
    all_status_files = []
    for line in lines:
        if not line.strip():
            continue
        # Format is: XY path or XY "path"
        # Let's extract path safely
        parts = line[3:].strip().strip('"')
        # If renamed, it might be path1 -> path2
        if " -> " in parts:
            parts = parts.split(" -> ")[1].strip().strip('"')
        all_status_files.append(parts)
        
    print(f"Total files in git status: {len(all_status_files)}")
    
    # Helper to check if a file has a suffix counterpart or is a suffix file itself
    def has_suffix_counterpart(path):
        dirname, filename = os.path.split(path)
        base, ext = os.path.splitext(filename)
        
        # Check if the filename itself is a suffix file (e.g. name_0.ext)
        if re.search(r'_\d+$', base):
            return True
            
        # Check if there is any file in the workspace directory status that matches name_\d+.ext
        # We look in the same directory
        for other_path in all_status_files:
            other_dir, other_file = os.path.split(other_path)
            if other_dir == dirname:
                other_base, other_ext = os.path.splitext(other_file)
                if other_ext == ext:
                    # Check if other_base is like base_\d+
                    match = re.match(r'^' + re.escape(base) + r'_(\d+)$', other_base)
                    if match:
                        return True
        return False

    to_stage = []
    skipped = []
    
    for path in all_status_files:
        # Ignore our scratch scripts
        if path.startswith("scratch/"):
            skipped.append((path, "scratch script"))
            continue
            
        if has_suffix_counterpart(path):
            skipped.append((path, "has/is _0 or _1 suffix counterpart"))
        else:
            to_stage.append(path)
            
    print(f"\nFiles to stage ({len(to_stage)}):")
    for path in to_stage:
        print(f"  - {path}")
        
    print(f"\nSkipped files ({len(skipped)}):")
    # Show first 10 skipped files for brevity
    for path, reason in skipped[:10]:
        print(f"  - {path} ({reason})")
    if len(skipped) > 10:
        print(f"  ... and {len(skipped) - 10} more skipped files.")
        
    # Stage the clean files
    if to_stage:
        print("\nStaging files...")
        for path in to_stage:
            full_path = os.path.join(workspace_dir, path)
            subprocess.run(["git", "add", path], cwd=workspace_dir)
        print("Staging complete.")
    else:
        print("\nNo files to stage.")

if __name__ == "__main__":
    main()
