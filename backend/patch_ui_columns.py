import os

path = r'c:\github\cobalt-multi-agent\backend\public\vli_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the thead block
old_thead = """                                <thead>
                                    <tr style="border-bottom: 1px solid rgba(255,255,255,0.1); color: var(--text-muted); text-align: left;">
                                        <th style="padding-bottom: 6px;">TICKER</th>
                                        <th style="padding-bottom: 6px;">GRADE</th>
                                        <th style="padding-bottom: 6px;">DIV YIELD</th>
                                        <th style="padding-bottom: 6px;">BETA</th>
                                    </tr>
                                </thead>"""

new_thead = """                                <thead>
                                    <tr style="border-bottom: 1px solid var(--card-border); color: var(--text-muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;">
                                        <th style="padding: 8px 4px; text-align: left;">SYMBOL</th>
                                        <th style="padding: 8px 4px; text-align: right;">PRICE</th>
                                        <th style="padding: 8px 4px; text-align: right;">VOLUME</th>
                                        <th style="padding: 8px 4px; text-align: right;">CHANGE</th>
                                        <th style="padding: 8px 4px; text-align: right;">DIV YIELD</th>
                                        <th style="padding: 8px 4px; text-align: right;">BETA</th>
                                        <th style="padding: 8px 4px; text-align: center;">GRADE</th>
                                    </tr>
                                </thead>"""
content = content.replace(old_thead, new_thead)

# Replace the tbody block
old_tbody = """                    tr.innerHTML = `
                        <td style="padding: 6px 0; font-family: var(--font-mono); color: var(--emerald-green); font-weight: bold; cursor: pointer;" onclick="document.getElementById('cli-input').value = 'analyze ' + '${c.symbol}'; document.getElementById('rt-btn').click();">${c.symbol}</td>
                        <td style="padding: 6px 0;">
                            <span style="background: rgba(63, 185, 80, 0.1); color: var(--emerald-green); padding: 2px 6px; border-radius: 4px; font-weight: 800;">${c.grade}</span>
                        </td>
                        <td style="padding: 6px 0;">${c.dividend_yield}%</td>
                        <td style="padding: 6px 0;">${c.beta}</td>
                    `;"""

new_tbody = """                    let gradeColor = '#3fb950'; // emerald-green fallback
                    let gradeBg = 'rgba(63, 185, 80, 0.1)';
                    let gradeBorder = 'rgba(63, 185, 80, 0.3)';
                    if (c.grade === 'S') { gradeColor = '#ffaa00'; gradeBg = 'rgba(255, 170, 0, 0.1)'; gradeBorder = 'rgba(255, 170, 0, 0.3)'; }
                    else if (c.grade === 'A+' || c.grade === 'A') { gradeColor = '#d866ff'; gradeBg = 'rgba(216, 102, 255, 0.1)'; gradeBorder = 'rgba(216, 102, 255, 0.3)'; }
                    else if (c.grade === 'B+' || c.grade === 'B') { gradeColor = '#00aaff'; gradeBg = 'rgba(0, 170, 255, 0.1)'; gradeBorder = 'rgba(0, 170, 255, 0.3)'; }
                    
                    let changeColor = 'var(--text-muted)';
                    let changeVal = c.change || '0%';
                    if (changeVal.includes('+')) changeColor = 'var(--emerald-green)';
                    else if (changeVal.includes('-')) changeColor = 'var(--ruby-red)';

                    let volFmt = c.volume;
                    if (c.volume >= 1000000) volFmt = (c.volume / 1000000).toFixed(1) + 'M';
                    else if (c.volume >= 1000) volFmt = (c.volume / 1000).toFixed(1) + 'K';

                    tr.innerHTML = `
                        <td style="padding: 4px; font-family: var(--font-mono); font-weight: bold; color: ${gradeColor}; cursor: pointer;" onclick="document.getElementById('cli-input').value = 'analyze ' + '${c.symbol}'; document.getElementById('rt-btn').click();">${c.symbol}</td>
                        <td style="padding: 4px; text-align: right;">$${(c.price || 0).toFixed(2)}</td>
                        <td style="padding: 4px; text-align: right;">${volFmt}</td>
                        <td style="padding: 4px; text-align: right; color: ${changeColor};">${changeVal}</td>
                        <td style="padding: 4px; text-align: right;">${c.dividend_yield}%</td>
                        <td style="padding: 4px; text-align: right;">${c.beta}</td>
                        <td style="padding: 4px; text-align: center;">
                            <span class="pulse-badge" style="background: ${gradeBg}; color: ${gradeColor}; border: 1px solid ${gradeBorder}; font-size: 9px; padding: 2px 6px;">${c.grade}</span>
                        </td>
                    `;"""
content = content.replace(old_tbody, new_tbody)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Column formatting updated successfully")
