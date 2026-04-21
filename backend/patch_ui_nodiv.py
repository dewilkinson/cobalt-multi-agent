import os

path = r'c:\github\cobalt-multi-agent\backend\public\VLI_session_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# Replace the thead block
old_thead = """                                <thead>
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

new_thead = """                                <thead>
                                    <tr style="border-bottom: 1px solid var(--card-border); color: var(--text-muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;">
                                        <th style="padding: 8px 4px; text-align: left;">SYMBOL</th>
                                        <th style="padding: 8px 4px; text-align: right;">PRICE</th>
                                        <th style="padding: 8px 4px; text-align: right;">VOLUME</th>
                                        <th style="padding: 8px 4px; text-align: right;">CHANGE</th>
                                        <th style="padding: 8px 4px; text-align: right;">BETA</th>
                                        <th style="padding: 8px 4px; text-align: center;">GRADE</th>
                                    </tr>
                                </thead>"""
content = content.replace(old_thead, new_thead)

# Replace the tbody block extraction
old_tbody = """                        <td style="padding: 4px; text-align: right;">${volFmt}</td>
                        <td style="padding: 4px; text-align: right; color: ${changeColor};">${changeVal}</td>
                        <td style="padding: 4px; text-align: right;">${c.dividend_yield}%</td>
                        <td style="padding: 4px; text-align: right;">${c.beta}</td>
                        <td style="padding: 4px; text-align: center;">"""

new_tbody = """                        <td style="padding: 4px; text-align: right;">${volFmt}</td>
                        <td style="padding: 4px; text-align: right; color: ${changeColor};">${changeVal}</td>
                        <td style="padding: 4px; text-align: right;">${c.beta}</td>
                        <td style="padding: 4px; text-align: center;">"""
content = content.replace(old_tbody, new_tbody)

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)
print("Removed Div Yield from UI!")
