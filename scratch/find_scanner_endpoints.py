import re

def main():
    filepath = "backend/src/server/app.py"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    print("Searching for routes in backend/src/server/app.py:")
    routes = re.findall(r'@app\.[a-z]+\([\'"]([a-zA-Z0-9_\-/{}]+)[\'"]', content)
    for r in sorted(set(routes)):
        if 'scanner' in r or 'strike' in r or 'combat' in r or 'pulse' in r:
            print(f"  {r}")
            
    # Check router inclusions
    inclusions = re.findall(r'include_router\([a-zA-Z0-9_]+', content)
    print("\nRouter inclusions:")
    for inc in inclusions:
        print(f"  {inc}")
        
    # Let's inspect backend/src/server/routes/scanner.py
    with open("backend/src/server/routes/scanner.py", 'r', encoding='utf-8') as f:
        scan_content = f.read()
    print("\nRoutes in scanner.py:")
    scan_routes = re.findall(r'@router\.[a-z]+\([\'"]([a-zA-Z0-9_\-/{}]+)[\'"]', scan_content)
    for r in sorted(set(scan_routes)):
        print(f"  {r}")

if __name__ == "__main__":
    main()
