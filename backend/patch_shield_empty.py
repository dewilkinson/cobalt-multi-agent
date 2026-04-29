import os

path = r'c:\github\cobalt-multi-agent\backend\public\vli_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

target = """                const tbody = table.querySelector('tbody');
                tbody.innerHTML = '';
                
                // ELITE GRADING LOGIC"""

replacement = """                const tbody = table.querySelector('tbody');
                tbody.innerHTML = '';
                
                if (res.candidates.length === 0) {
                    tbody.innerHTML = `<tr style="border: none;"><td colspan="6" style="text-align: center; padding: 30px 10px; color: var(--text-muted); font-style: italic;">Scanner cache cleared. Standing by...</td></tr>`;
                }
                
                // ELITE GRADING LOGIC"""

if target in content:
    content = content.replace(target, replacement)
    
    # Also add the else-if reset block for SHIELD if it's missing (Wait, I added it earlier to SATELLITE, let me check if SHIELD needs it)
    sh_target = """                if (candidates.length > 0) {
                    const existingSymbols = new Set(activeShieldCandidates.map(c => c.symbol));
                    const newCandidates = candidates.filter(c => !existingSymbols.has(c.symbol));
                    
                    if (newCandidates.length > 0) {
                        newCandidates.forEach(c => window.vliNewSymbols.add(c.symbol));
                        activeShieldCandidates = [...activeShieldCandidates, ...newCandidates];
                        updateShieldResultsUI();
                        console.log(`[VLI_SHIELD] Auto-Refresh: ${newCandidates.length} new signals merged silently.`);
                    }
                }
            }"""
    sh_repl = """                if (candidates.length > 0) {
                    const existingSymbols = new Set(activeShieldCandidates.map(c => c.symbol));
                    const newCandidates = candidates.filter(c => !existingSymbols.has(c.symbol));
                    
                    if (newCandidates.length > 0) {
                        newCandidates.forEach(c => window.vliNewSymbols.add(c.symbol));
                        activeShieldCandidates = [...activeShieldCandidates, ...newCandidates];
                        updateShieldResultsUI();
                        console.log(`[VLI_SHIELD] Auto-Refresh: ${newCandidates.length} new signals merged silently.`);
                    }
                } else if (candidates.length === 0 && activeShieldCandidates.length > 0) {
                    activeShieldCandidates = [];
                    updateShieldResultsUI();
                    console.log(`[VLI_SHIELD] Auto-Refresh: Scanner state cleared.`);
                }
            }"""
    if sh_target in content:
        content = content.replace(sh_target, sh_repl)

    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Patched SHIELD empty state UI")
else:
    print("Target not found.")
