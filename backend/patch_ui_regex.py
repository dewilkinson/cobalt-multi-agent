import os

path = r'c:\github\cobalt-multi-agent\backend\public\vli_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = r"if (/^\s*(run|start)\s+(market\s+)?scan\s*[.!?]?\s*$/i.test(requestText)) {"
repl = r"if (/^\s*(run|start|generate)\s+(market\s+|full\s+)?scan\s*[.!?]?\s*$/i.test(requestText)) {"

if target in content:
    content = content.replace(target, repl)
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced UI Regex successfully.")
else:
    print("Target regex not found in HTML!")
