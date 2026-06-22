import os
import ast

def check_python_files(directory):
    corrupted_files = []
    print(f"Scanning directory: {directory}")
    for root, dirs, files in os.walk(directory):
        # Skip virtual environment folders
        if '.venv' in root or 'node_modules' in root or '.git' in root:
            continue
        for file in files:
            if file.endswith('.py'):
                filepath = os.path.join(root, file)
                try:
                    with open(filepath, 'rb') as f:
                        content = f.read()
                    
                    # Check for null bytes
                    if b'\x00' in content:
                        print(f"[CORRUPT - NULL BYTES]: {filepath}")
                        corrupted_files.append((filepath, "Contains null bytes"))
                        continue
                    
                    # Try to parse the AST to check for syntax errors
                    try:
                        ast.parse(content, filename=filepath)
                    except SyntaxError as se:
                        print(f"[SYNTAX ERROR]: {filepath} - Line {se.lineno}: {se.msg}")
                        corrupted_files.append((filepath, f"SyntaxError: {se.msg} at line {se.lineno}"))
                except Exception as e:
                    print(f"[ERROR READING]: {filepath} - {e}")
                    corrupted_files.append((filepath, f"Read Error: {e}"))
                    
    print("\n=== Scan Complete ===")
    if corrupted_files:
        print(f"Found {len(corrupted_files)} corrupted/invalid files:")
        for path, err in corrupted_files:
            print(f"- {path}: {err}")
    else:
        print("All Python files are syntax-valid and clean!")

if __name__ == "__main__":
    check_python_files(".")
