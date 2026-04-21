import os

path = r'c:\github\cobalt-multi-agent\backend\src\server\app.py'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = r'm = re.search(r"(?:^|GET\s+|PRICE\s+OF\s+)\$?([A-Z0-9.\-_=]{1,20})(?:\s+PRICE)?$", cleaned_input)'
repl = r'm = re.search(r"^(?:GET\s+|PRICE\s+OF\s+)?\$?([A-Z0-9.\-_=]{1,20})(?:\s+PRICE)?$", cleaned_input)'

content = content.replace(target, repl)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Fixed regex bypassing")
