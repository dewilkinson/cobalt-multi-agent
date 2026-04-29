import re
import os

path = r'c:\github\cobalt-multi-agent\backend\public\vli_dashboard.html'
with open(path, 'r', encoding='utf-8') as f:
    content = f.read()

# 1. Rename the titles in CARD_TYPES
content = content.replace(
    "'SCAN_RES': { idPrefix: 'SR', title: 'SATELLITE', isSingleton: true }",
    "'SCAN_RES': { idPrefix: 'SR', title: 'Scanner Results - Satellite', isSingleton: true }"
)
content = content.replace(
    "'SHIELD_RES': { idPrefix: 'SH', title: 'CORE', isSingleton: true }",
    "'SHIELD_RES': { idPrefix: 'SH', title: 'Scanner Results - Core', isSingleton: true }"
)

# 2. Automatically spawn SHIELD_RES and SCAN_RES if they don't exist in the loaded workspace
startup_inject = """
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'SCAN_RES')) {
                 UXManager.createCard('SCAN_RES', {top: '2%', left: '33.5%', width: '31%', height: '47%'}, 'scanner');
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'SHIELD_RES')) {
                 UXManager.createCard('SHIELD_RES', {top: '51%', left: '33.5%', width: '31%', height: '47%'}, 'shield');
            }
"""

# Insert inside the init Dashboard or loadWorkspace loop. 
# We'll put it right after the loop in `loadWorkspace` that parses `state`.
# Find 'updateViewMenu();' inside loadWorkspace and prepend startup_inject.
content = content.replace(
    "                updateViewMenu();",
    startup_inject + "\n                updateViewMenu();"
)

# And to be safe, add them to the manual summon list
summon_inject = """
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'SCAN_RES')) {
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="UXManager.createCard('SCAN_RES')" style="color:var(--emerald-green);">[+] Spawn Satellite Scanner</div>`;
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'SHIELD_RES')) {
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="UXManager.createCard('SHIELD_RES')" style="color:var(--emerald-green);">[+] Spawn Core Scanner</div>`;
            }
"""
content = content.replace(
    "if (keys.length > 0) viewMenu.innerHTML += '<div class=\"dropdown-divider\"></div>';",
    summon_inject + "\n            if (keys.length > 0) viewMenu.innerHTML += '<div class=\"dropdown-divider\"></div>';"
)


open(path, 'w', encoding='utf-8').write(content)
print("UI Names and Auto-Spawn Patched")
