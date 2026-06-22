import ast

def inspect_file(filename):
    with open(filename, 'r', encoding='utf-8') as f:
        tree = ast.parse(f.read(), filename=filename)
        
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            is_tool = any(isinstance(d, ast.Name) and d.id == 'tool' for d in node.decorator_list)
            is_tool_call = any(isinstance(d, ast.Call) and isinstance(d.func, ast.Name) and d.func.id == 'tool' for d in node.decorator_list)
            
            docstring = ast.get_docstring(node)
            first_line = docstring.split('\n')[0] if docstring else "No docstring"
            
            print(f"{'Async ' if isinstance(node, ast.AsyncFunctionDef) else ''}Function: {node.name}")
            if is_tool or is_tool_call:
                print(f"  [TOOL]")
            print(f"  Doc: {first_line}")

if __name__ == "__main__":
    inspect_file("backend/src/tools/scanner.py")
