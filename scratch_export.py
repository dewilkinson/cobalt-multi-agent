import subprocess
import sys
import os

if __name__ == '__main__':
    project_root = os.path.abspath(os.path.dirname(__file__))
    script_path = os.path.join(project_root, 'scripts', 'export_tradezella.py')
    
    # Delegate standard arguments to the consolidated scripts/export_tradezella.py
    cmd = [sys.executable, script_path] + sys.argv[1:]
    res = subprocess.run(cmd)
    sys.exit(res.returncode)
