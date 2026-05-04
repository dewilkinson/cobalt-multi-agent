import os
import glob

def rename_in_file(filepath):
    try:
        with open(filepath, 'r', encoding='utf-8') as f:
            content = f.read()
    except UnicodeDecodeError:
        try:
            with open(filepath, 'r', encoding='utf-16') as f:
                content = f.read()
        except:
            return
            
    new_content = content.replace("SCANNER_COMBAT_LIST", "SCANNER_STRIKE_LIST")
    new_content = new_content.replace("combat_list", "strike_list")
    
    if new_content != content:
        # Determine encoding based on original file success
        encoding = 'utf-8' if 'utf-8' in filepath or filepath.endswith('.html') else 'utf-8' # simplified
        try:
            with open(filepath, 'w', encoding='utf-8') as f:
                f.write(new_content)
            print(f"Updated {filepath}")
        except:
            try:
                with open(filepath, 'w', encoding='utf-16') as f:
                    f.write(new_content)
                print(f"Updated {filepath} (utf-16)")
            except Exception as e:
                print(f"Failed to write {filepath}: {e}")

for root, dirs, files in os.walk("backend"):
    if ".venv" in root or ".git" in root or "__pycache__" in root:
        continue
    for file in files:
        if file.endswith(".py") or file.endswith(".html") or file.endswith(".js"):
            rename_in_file(os.path.join(root, file))

# Rename the actual files
data_dir = os.path.join("backend", "data")
if os.path.exists(data_dir):
    old_path = os.path.join(data_dir, "SCANNER_COMBAT_LIST.json")
    new_path = os.path.join(data_dir, "SCANNER_STRIKE_LIST.json")
    if os.path.exists(old_path):
        os.rename(old_path, new_path)
        print(f"Renamed {old_path} to {new_path}")
