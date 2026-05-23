import os

path = r'C:\Users\rende\.gemini\antigravity\worktrees\cobalt-multi-agent\backend\public\vli_dashboard.html'

with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# First replace the initial graying out
target_1 = """                    if (c.is_miss) {
                        tr.style.opacity = '0.35';
                        tr.style.filter = 'grayscale(1)';
                    }"""
content = content.replace(target_1, "")

# Second replace the hover state
target_2 = """                        if (c.is_miss) {
                            tr.style.opacity = '0.8';
                            tr.style.filter = 'grayscale(0.5)';
                        }"""
content = content.replace(target_2, "")

# Third replace the leave state
target_3 = """                        if (c.is_miss) {
                            tr.style.opacity = '0.35';
                            tr.style.filter = 'grayscale(1)';
                        }"""
content = content.replace(target_3, "")

# Finally the gradeBg wipe
target_4 = """                    if (c.is_miss) {
                        gradeBg = 'transparent';
                        gradeBorder = 'rgba(255,255,255,0.05)';
                    }"""
content = content.replace(target_4, "")

with open(path, 'w', encoding='utf-8') as f:
    f.write(content)

print(f"Patched opacity and grayscale logic out of VLI UI!")
