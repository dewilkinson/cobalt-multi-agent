import re

with open("backend/public/VLI_session_dashboard.html", "r", encoding="utf-8") as f:
    content = f.read()

# 1. Initialize the set where activeScannerCandidates is defined
content = content.replace(
    'let activeScannerCandidates = [];',
    'let activeScannerCandidates = [];\n        window.vliNewSymbols = window.vliNewSymbols || new Set();'
)

# 2. Reset the set when activeScannerCandidates gets reset
content = content.replace(
    'activeScannerCandidates = [];',
    'activeScannerCandidates = []; window.vliNewSymbols.clear();'
)

# 3. Replace setting c.isNew = true -> add to set
content = content.replace(
    'newCandidates.forEach(c => c.isNew = true);',
    'newCandidates.forEach(c => window.vliNewSymbols.add(c.symbol));'
)

# 4. Modify renderScannerResults to pull from the set
old_render_logic = """
                    const tr = document.createElement('tr');
                    tr.style.cursor = 'pointer';
                    tr.className = c.isNew ? 'scanner-res-row new-candidate-highlight' : 'scanner-res-row';
                    tr.style.transition = 'background 0.3s ease';
                    
                    tr.onmouseenter = () => {
                        if (c.isNew) {
                            tr.classList.remove('new-candidate-highlight');
                            c.isNew = false;
                        }
"""
new_render_logic = """
                    c.isNew = window.vliNewSymbols.has(c.symbol);
                    const tr = document.createElement('tr');
                    tr.style.cursor = 'pointer';
                    tr.className = c.isNew ? 'scanner-res-row new-candidate-highlight' : 'scanner-res-row';
                    tr.style.transition = 'background 0.3s ease';
                    
                    tr.onmouseenter = () => {
                        if (window.vliNewSymbols.has(c.symbol)) {
                            tr.classList.remove('new-candidate-highlight');
                            window.vliNewSymbols.delete(c.symbol);
                            c.isNew = false;
                        }
"""
content = content.replace(old_render_logic, new_render_logic)

with open("backend/public/VLI_session_dashboard.html", "w", encoding="utf-8") as f:
    f.write(content)

print("Replaced!")
