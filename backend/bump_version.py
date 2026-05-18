import os
import re
import hashlib

BASE_DIR = os.path.dirname(__file__)
VERSION_FILE = os.path.join(BASE_DIR, 'src', 'version.py')
HTML_FILE = os.path.join(BASE_DIR, 'public', 'vli_dashboard.html')
REACT_VERSION_FILE = os.path.join(BASE_DIR, '..', 'web', 'src', 'core', 'config', 'version.ts')
HASH_FILE = os.path.join(BASE_DIR, '.version_hash')

def get_dir_hash():
    hasher = hashlib.md5()
    dirs_to_hash = [
        os.path.join(BASE_DIR, 'src'),
        os.path.join(BASE_DIR, 'public'),
        os.path.join(BASE_DIR, '..', 'web', 'src')
    ]
    for root_dir in dirs_to_hash:
        if not os.path.exists(root_dir):
            continue
        for root, _, files in os.walk(root_dir):
            for f in sorted(files):
                if f.endswith(('.py', '.html', '.js', '.css', '.ts', '.tsx')) and f != 'version.py' and f != 'version.ts':
                    filepath = os.path.join(root, f)
                    with open(filepath, 'rb') as file_obj:
                        content = file_obj.read()
                        if f == 'vli_dashboard.html':
                            content = re.sub(rb'const VLI_CLIENT_VERSION\s*=\s*"[^"]+";', b'', content)
                        hasher.update(content)
    return hasher.hexdigest()

current_hash = get_dir_hash()
old_hash = ""
if os.path.exists(HASH_FILE):
    with open(HASH_FILE, 'r') as f:
        old_hash = f.read().strip()

if current_hash == old_hash:
    print("Code unchanged. Skipping version bump.")
    exit(0)

def bump_version_string(v_str):
    parts = v_str.split('.')
    last_part = parts[-1]
    new_last = str(int(last_part) + 1).zfill(len(last_part))
    parts[-1] = new_last
    return '.'.join(parts)

with open(VERSION_FILE, 'r') as f:
    content = f.read()

match = re.search(r'SERVER_VERSION\s*=\s*"([^"]+)"', content)
if not match:
    print("Could not find SERVER_VERSION")
    exit(1)

old_version = match.group(1)
new_version = bump_version_string(old_version)

new_content = content.replace(f'SERVER_VERSION = "{old_version}"', f'SERVER_VERSION = "{new_version}"')
with open(VERSION_FILE, 'w') as f:
    f.write(new_content)

with open(HTML_FILE, 'r', encoding='utf-8') as f:
    html_content = f.read()

html_content = re.sub(
    r'const VLI_CLIENT_VERSION\s*=\s*"[^"]+";',
    f'const VLI_CLIENT_VERSION = "{new_version}";',
    html_content
)

with open(HTML_FILE, 'w', encoding='utf-8') as f:
    f.write(html_content)

if os.path.exists(REACT_VERSION_FILE):
    with open(REACT_VERSION_FILE, 'r', encoding='utf-8') as f:
        react_content = f.read()
    react_content = re.sub(
        r'export const CLIENT_VERSION\s*=\s*"[^"]+";',
        f'export const CLIENT_VERSION = "{new_version}";',
        react_content
    )
    with open(REACT_VERSION_FILE, 'w', encoding='utf-8') as f:
        f.write(react_content)

with open(HASH_FILE, 'w') as f:
    f.write(current_hash)

print(f"Code changes detected. Bumped version from {old_version} to {new_version}")
