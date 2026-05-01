import os
import re
import hashlib

BASE_DIR = os.path.dirname(__file__)
VERSION_FILE = os.path.join(BASE_DIR, 'src', 'version.py')
HTML_FILE = os.path.join(BASE_DIR, 'public', 'vli_dashboard.html')
HASH_FILE = os.path.join(BASE_DIR, '.version_hash')

def get_dir_hash():
    hasher = hashlib.md5()
    for root_dir in [os.path.join(BASE_DIR, 'src'), os.path.join(BASE_DIR, 'public')]:
        for root, _, files in os.walk(root_dir):
            for f in sorted(files):
                if f.endswith(('.py', '.html', '.js', '.css')) and f != 'version.py':
                    filepath = os.path.join(root, f)
                    with open(filepath, 'rb') as file_obj:
                        content = file_obj.read()
                        if f == 'vli_dashboard.html':
                            # Exclude the version string from the hash so bumping doesn't trigger endless bumps
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

with open(HASH_FILE, 'w') as f:
    f.write(current_hash)

print(f"Code changes detected. Bumped version from {old_version} to {new_version}")
