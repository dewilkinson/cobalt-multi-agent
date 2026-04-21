import re

with open("backend/public/VLI_session_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# Fix the bug
content = content.replace(
    '''let activeScannerCandidates = []; window.vliNewSymbols.clear();
        window.vliNewSymbols = window.vliNewSymbols || new Set();''',
    '''window.vliNewSymbols = window.vliNewSymbols || new Set();
        let activeScannerCandidates = []; 
        window.vliNewSymbols.clear();'''
)

# And fix the duplicate
content = content.replace(
    'window.vliNewSymbols.clear();\n        window.vliNewSymbols = window.vliNewSymbols || new Set();',
    'window.vliNewSymbols = window.vliNewSymbols || new Set();\n        window.vliNewSymbols.clear();'
)

with open("backend/public/VLI_session_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Fixed initialization order!")
