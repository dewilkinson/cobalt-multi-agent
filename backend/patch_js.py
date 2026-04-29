import os

path = r'c:\github\cobalt-multi-agent\backend\public\vli_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

shield_render = """
        // 1d. Shield Results UI
        let activeShieldCandidates = [];
        window.vliNewShieldSymbols = new Set();
        
        function renderShieldResults(data) {
            if (!data.scanner_results || !data.scanner_results.candidates) return;
            const res = data.scanner_results;
            
            document.querySelectorAll('.card[data-type-guid="SHIELD_RES"]').forEach(card => {
                let body = card.querySelector('.card-body');
                if (!body) {
                    body = document.createElement('div');
                    body.className = 'card-body';
                    body.style.overflowY = 'auto';
                    body.style.padding = '10px';
                    body.style.height = 'calc(100% - 30px)';
                    card.appendChild(body);
                }
                
                let table = body.querySelector('table');
                if (!table) {
                    body.innerHTML = `
                        <div style="font-size: 11px; margin-bottom: 12px; color: var(--text-muted); display: flex; justify-content: space-between; align-items: center;">
                            <div>Pulse Mode: <span style="color: var(--emerald-green); font-weight: 800;">Defensive Shield</span></div>
                            <div style="font-family: var(--font-mono); font-size: 10px;">MATCHES: <span id="sh-match-count" style="color: var(--emerald-green); font-weight: 800;">${res.candidates.length}</span></div>
                        </div>
                        <div class="table-responsive">
                            <table class="table" style="font-size: 11px; width: 100%; border-collapse: collapse;">
                                <thead>
                                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted); text-align: left;">
                                        <th style="padding-bottom: 6px;">TICKER</th>
                                        <th style="padding-bottom: 6px;">GRADE</th>
                                        <th style="padding-bottom: 6px;">DIV YIELD</th>
                                        <th style="padding-bottom: 6px;">BETA</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                        </div>
                    `;
                    table = body.querySelector('table');
                }
                
                const tbody = table.querySelector('tbody');
                tbody.innerHTML = '';
                
                res.candidates.forEach(c => {
                    const tr = document.createElement('tr');
                    tr.style.borderBottom = '1px solid rgba(255,255,255,0.05)';
                    
                    const isNew = window.vliNewShieldSymbols.has(c.symbol);
                    if (isNew) {
                        tr.style.background = 'rgba(63, 185, 80, 0.15)';
                        tr.style.transition = 'background 0.5s ease';
                        setTimeout(() => { tr.style.background = 'transparent'; window.vliNewShieldSymbols.delete(c.symbol); }, 2000);
                    }

                    tr.innerHTML = `
                        <td style="padding: 6px 0; font-family: var(--font-mono); color: var(--emerald-green); font-weight: bold; cursor: pointer;" onclick="document.getElementById('cli-input').value = 'analyze ' + '${c.symbol}'; document.getElementById('rt-btn').click();">${c.symbol}</td>
                        <td style="padding: 6px 0;">
                            <span style="background: rgba(63, 185, 80, 0.1); color: var(--emerald-green); padding: 2px 6px; border-radius: 4px; font-weight: 800;">${c.grade}</span>
                        </td>
                        <td style="padding: 6px 0;">${c.dividend_yield}%</td>
                        <td style="padding: 6px 0;">${c.beta}</td>
                    `;
                    tbody.appendChild(tr);
                });
                
                document.getElementById('sh-match-count').innerText = res.candidates.length;
            });
        }
        
        function updateShieldResultsUI() {
            renderShieldResults({
                scanner_results: {
                    pulse_mode: "Defensive Shield",
                    candidates: activeShieldCandidates
                }
            });
        }
        
        async function autoRefreshShieldResults() {
            try {
                const response = await fetch('/api/scanner/shield-bunker');
                if (!response.ok) return;
                const data = await response.json();
                
                const candidates = data.data || [];
                
                if (candidates.length > 0) {
                    const existingSymbols = new Set(activeShieldCandidates.map(c => c.symbol));
                    const newCandidates = candidates.filter(c => !existingSymbols.has(c.symbol));
                    
                    if (newCandidates.length > 0) {
                        newCandidates.forEach(c => window.vliNewShieldSymbols.add(c.symbol));
                        activeShieldCandidates = [...activeShieldCandidates, ...newCandidates];
                        updateShieldResultsUI();
                    } else if (candidates.length > 0 && activeShieldCandidates.length === 0) {
                        // Startup bypass
                        activeShieldCandidates = [...candidates];
                        updateShieldResultsUI();
                    }
                } else if (candidates.length === 0 && activeShieldCandidates.length > 0) {
                    activeShieldCandidates = [];
                    updateShieldResultsUI();
                }
            } catch (e) {
                console.warn('[VLI_SHIELD] Silent state poll failed.', e);
            }
        }
        
        setInterval(autoRefreshShieldResults, 10000);
        setTimeout(autoRefreshShieldResults, 1500); // Kickoff immediately on boot
        
        // --- End of Shield Logic ---
"""

if "function renderShieldResults" not in content:
    content = content.replace("</script>", shield_render + "\n    </script>")
    with open(path, 'w', encoding='utf-8') as f:
        f.write(content)
    print("Shield JS Loop Injected.")
else:
    print("already exists")
