import json
import os
import re

ROOT_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
VERSION_JSON = os.path.join(ROOT_DIR, 'version.json')
BACKEND_VER_FILE = os.path.join(ROOT_DIR, 'backend', 'src', 'version.py')
FRONTEND_VER_FILE = os.path.join(ROOT_DIR, 'web', 'src', 'core', 'config', 'version.ts')
PACKAGE_JSON_FILE = os.path.join(ROOT_DIR, 'web', 'package.json')

def load_version():
    with open(VERSION_JSON, 'r') as f:
        data = json.load(f)
    return data['version']

def increment_version(version_str):
    parts = version_str.split('.')
    if len(parts) == 3:
        major, minor, build = parts
        build = str(int(build) + 1).zfill(4)
        return f"{major}.{minor}.{build}"
    return version_str

def save_version(new_version):
    with open(VERSION_JSON, 'w') as f:
        json.dump({'version': new_version}, f, indent=2)

def update_backend(version):
    os.makedirs(os.path.dirname(BACKEND_VER_FILE), exist_ok=True)
    with open(BACKEND_VER_FILE, 'w') as f:
        f.write(f'SERVER_VERSION = "{version}"\n')

def update_frontend_ts(version):
    os.makedirs(os.path.dirname(FRONTEND_VER_FILE), exist_ok=True)
    with open(FRONTEND_VER_FILE, 'w') as f:
        f.write(f'export const CLIENT_VERSION = "{version}";\n')

def update_package_json(version):
    if os.path.exists(PACKAGE_JSON_FILE):
        with open(PACKAGE_JSON_FILE, 'r') as f:
            content = f.read()
        
        # Replace version "X.Y.Z" with our version format
        content = re.sub(r'"version":\s*"[^"]*"', f'"version": "{version}"', content)
        
        with open(PACKAGE_JSON_FILE, 'w') as f:
            f.write(content)

def update_vli_dashboard(version):
    dashboard_file = os.path.join(ROOT_DIR, 'backend', 'public', 'vli_dashboard.html')
    if os.path.exists(dashboard_file):
        with open(dashboard_file, 'r', encoding='utf-8') as f:
            content = f.read()
            
        content = re.sub(r'const VLI_CLIENT_VERSION = "[^"]*";', f'const VLI_CLIENT_VERSION = "{version}";', content)
        
        with open(dashboard_file, 'w', encoding='utf-8') as f:
            f.write(content)

if __name__ == '__main__':
    current_version = load_version()
    new_version = increment_version(current_version)
    save_version(new_version)
    update_backend(new_version)
    update_frontend_ts(new_version)
    update_package_json(new_version)
    update_vli_dashboard(new_version)
    print(f"Version synchronized: {new_version}")
