def main():
    filepath = "backend/src/server/routes/scanner.py"
    with open(filepath, 'r', encoding='utf-8') as f:
        content = f.read()
        
    import ast
    tree = ast.parse(content, filename=filepath)
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            # Check if it has @router decorator
            has_route = any(isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ['get', 'post', 'delete', 'put'] for d in node.decorator_list)
            if has_route:
                decorator = [ast.unparse(d) for d in node.decorator_list if isinstance(d, ast.Call) and isinstance(d.func, ast.Attribute) and d.func.attr in ['get', 'post', 'delete', 'put']][0]
                docstring = ast.get_docstring(node)
                first_line = docstring.split('\n')[0] if docstring else "No docstring"
                print(f"Route: {decorator} -> {node.name}")
                print(f"  Doc: {first_line}")

if __name__ == "__main__":
    main()
