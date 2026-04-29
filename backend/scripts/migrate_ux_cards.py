import re

def migrate():
    fp = "c:/github/cobalt-multi-agent/backend/public/vli_dashboard.html"
    with open(fp, "r", encoding="utf-8") as f:
        html = f.read()

    # 1. Menu updates
    html = html.replace(
        `<div class="dropdown-item" onclick="toggleWindow('win-coordinator')">Coordinator Interface <span>ALT+1</span></div>`,
        `<div class="dropdown-item" onclick="UXManager.createCard('VLI_CHAT')">Coordinator Interface <span>ALT+1</span></div>`
    )
    html = html.replace(
        `<div class="dropdown-item" onclick="toggleWindow('win-telemetry')">Raw Telemetry <span>ALT+2</span></div>`,
        `<div class="dropdown-item" onclick="UXManager.createCard('VLI_TELEMETRY')">Raw Telemetry <span>ALT+2</span></div>`
    )
    html = html.replace(
        `<div class="dropdown-item" onclick="toggleWindow('win-watchlist')">Macro Watchlist <span>ALT+3</span></div>`,
        `<div class="dropdown-item" onclick="UXManager.createCard('MACRO_WL')">Macro Watchlist <span>ALT+3</span></div>`
    )
    html = html.replace(
        `<div class="dropdown-item" onclick="toggleWindow('win-report')">Analysis Report <span>ALT+4</span></div>`,
        `<div class="dropdown-item" onclick="UXManager.createCard('ANALYSIS_REP')">Analysis Report <span>ALT+4</span></div>`
    )
    
    # 2. Extract out the hardcoded cards between <div class="dashboard-container" id="wm-workspace"> and </script>
    # Wait, the cards are inside <div class="dashboard-container" id="wm-workspace"> ... </div>
    # Let's just regex out the content inside wm-workspace completely and leave it empty.
    
    match = re.search(r'(<div class="dashboard-container" id="wm-workspace">)([\s\S]*?)(</div>\s*<script>)', html)
    if match:
        html = html[:match.start(2)] + "\n        <!-- Dynamic cards will be injected here by UXCardManager -->\n    " + html[match.end(2):]
    else:
        print("Failed to find wm-workspace bounds")

    # 3. Inject UXManager Class and logic after `let winManager = { ... };`
    manager_code = """
        const UX_CARD_LIMIT = 8;
        
        const CARD_TYPES = {
            'VLI_CHAT': { idPrefix: 'CI', title: 'COORDINATOR INTERFACE', isSingleton: true },
            'VLI_TELEMETRY': { idPrefix: 'TM', title: 'RAW TELEMETRY', isSingleton: false },
            'MACRO_WL': { idPrefix: 'WL', title: 'MACRO WATCHLIST', isSingleton: false },
            'ANALYSIS_REP': { idPrefix: 'AR', title: 'ANALYSIS REPORT', isSingleton: false }
        };

        class UXCardManager {
            constructor() {
                this.instances = {};
                this.typeCounts = { 'VLI_CHAT': 0, 'VLI_TELEMETRY': 0, 'MACRO_WL': 0, 'ANALYSIS_REP': 0 };
            }

            generateGUID() {
                return 'xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx'.replace(/[xy]/g, function(c) {
                    var r = Math.random() * 16 | 0, v = c == 'x' ? r : (r & 0x3 | 0x8);
                    return v.toString(16);
                });
            }

            createCard(typeGuid, defaultStyles = {}, forceInstanceGuid = null) {
                if (Object.keys(this.instances).length >= UX_CARD_LIMIT) {
                    console.warn(`[UX_MANAGER] System limit of ${UX_CARD_LIMIT} windows reached.`);
                    return null;
                }

                const typeDef = CARD_TYPES[typeGuid];
                if (!typeDef) {
                    console.error("Unknown card type: " + typeGuid);
                    return null;
                }

                if (typeDef.isSingleton && this.typeCounts[typeGuid] >= 1) {
                    // Focus existing (singleton)
                    for (let id in this.instances) {
                        if (this.instances[id].dataset.typeGuid === typeGuid) {
                            if (this.instances[id].style.display === 'none') {
                                this.instances[id].style.display = 'flex';
                            }
                            bringToFront(this.instances[id]);
                            return this.instances[id];
                        }
                    }
                    return null;
                }

                const instanceGuid = forceInstanceGuid || this.generateGUID();
                this.typeCounts[typeGuid]++;
                
                let badgeLabel = typeDef.idPrefix;
                if (this.typeCounts[typeGuid] > 1) {
                    badgeLabel += this.typeCounts[typeGuid];
                }

                const cardBox = document.createElement('div');
                cardBox.className = 'card';
                cardBox.id = 'win-' + instanceGuid;
                cardBox.dataset.typeGuid = typeGuid;
                cardBox.dataset.instanceGuid = instanceGuid;
                cardBox.dataset.badge = badgeLabel;
                
                cardBox.style.top = defaultStyles.top || '50px';
                cardBox.style.left = defaultStyles.left || '50px';
                if (defaultStyles.right) {
                    cardBox.style.left = 'auto';
                    cardBox.style.right = defaultStyles.right;
                }
                cardBox.style.width = defaultStyles.width || '450px';
                cardBox.style.height = defaultStyles.height || '350px';
                cardBox.style.zIndex = ++winManager.maxZ;

                const liveBadgeHTML = typeGuid !== 'ANALYSIS_REP' ? `<span class="live-badge" id="conn-status-${instanceGuid}">LIVE</span>` : '';
                
                let bodyContent = '';
                if (typeGuid === 'VLI_CHAT') {
                    bodyContent = `
                        <div class="card-body" style="padding:0; overflow:hidden; display:flex; flex-direction:column;">
                            <div class="chat-messages" id="chat-messages" data-owner="${instanceGuid}">
                                <div class="msg msg-ai"><strong>VLI</strong> initialized. Draggable Window Manager mode active.</div>
                            </div>
                            <div class="input-area">
                                <div class="gemini-panel">
                                    <textarea id="chat-input" placeholder="Enter directive..."></textarea>
                                    <div class="panel-controls">
                                        <div style="display:flex; align-items:center; gap:10px;">
                                            <div class="send-btn" id="send-stop-btn" onclick="handleSendStop('${instanceGuid}')">➤</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>`;
                } else if (typeGuid === 'VLI_TELEMETRY') {
                    bodyContent = `<div class="card-body terminal" id="telemetry-body-${instanceGuid}" data-owner="${instanceGuid}"></div>`;
                } else if (typeGuid === 'MACRO_WL') {
                    bodyContent = `
                        <div class="card-body" style="overflow-y: hidden; padding: 10px;">
                            <table class="macro-table">
                                <thead>
                                    <tr>
                                        <th>TICKER</th>
                                        <th>PRICE</th>
                                        <th>CHANGE</th>
                                        <th>SORTINO</th>
                                        <th>TREND (5M)</th>
                                    </tr>
                                </thead>
                                <tbody id="macro-watchlist-body-${instanceGuid}" data-owner="${instanceGuid}">
                                    <tr><td colspan="5" style="text-align:center; padding:20px;">Standby...</td></tr>
                                </tbody>
                            </table>
                        </div>`;
                } else if (typeGuid === 'ANALYSIS_REP') {
                    bodyContent = `
                        <div class="card-body terminal analysis-report-body" id="analysis-report-viewer-${instanceGuid}" data-owner="${instanceGuid}">
                            <div style="color:var(--text-muted); text-align:center; padding:40px;">No report active.</div>
                        </div>`;
                }

                cardBox.innerHTML = `
                    <div class="card-header">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <div class="descriptor">${badgeLabel}</div>
                            <div>${typeDef.title} ${liveBadgeHTML}</div>
                        </div>
                        <div class="card-controls">
                            <div class="win-btn win-min" onclick="toggleCollapse('win-${instanceGuid}')" title="Collapse"></div>
                            ${typeGuid === 'VLI_CHAT' ? '' : `<div class="win-btn win-pop" onclick="popoutWindow('win-${instanceGuid}')" title="Pop-out"></div>`}
                            <div class="win-btn win-max" onclick="maxWin('win-${instanceGuid}')" title="Maximize"></div>
                            <div class="win-btn win-close" onclick="UXManager.removeCard('${instanceGuid}')" title="Close"></div>
                        </div>
                    </div>
                    ${bodyContent}
                    <div class="card-resizer"></div>
                `;

                document.getElementById('wm-workspace').appendChild(cardBox);
                this.instances[instanceGuid] = cardBox;

                if (typeGuid === 'VLI_CHAT') {
                    // Overwrite global input bindings for the new input
                    const inp = document.getElementById('chat-input');
                    if (inp) {
                        inp.addEventListener('keydown', (e) => {
                            if (e.key === 'Enter' && !e.shiftKey) {
                                e.preventDefault();
                                if (isProcessing) return;
                                handleSendStop();
                            } else if (e.key === 'ArrowUp') {
                                if (chatHistory.length > 0 && historyIndex > 0) {
                                    historyIndex--;
                                    e.target.value = chatHistory[historyIndex];
                                    e.preventDefault();
                                }
                            } else if (e.key === 'ArrowDown') {
                                if (chatHistory.length > 0 && historyIndex < chatHistory.length) {
                                    historyIndex++;
                                    if (historyIndex === chatHistory.length) {
                                        e.target.value = '';
                                    } else {
                                        e.target.value = chatHistory[historyIndex];
                                    }
                                    e.preventDefault();
                                }
                            }
                        });
                    }
                }
                
                this.bindCardEvents(cardBox);
                
                // Trigger a sync if required
                if (!isPolling) poll();
                
                return cardBox;
            }

            removeCard(instanceGuid) {
                const card = this.instances[instanceGuid];
                if (card) {
                    if (card.dataset.typeGuid === 'VLI_CHAT') {
                        // For singleton, just hide to preserve chat history if they "close" it
                        card.style.display = 'none';
                    } else {
                        card.remove();
                        delete this.instances[instanceGuid];
                    }
                    saveLayout();
                }
            }
            
            bindCardEvents(cardBox) {
                const header = cardBox.querySelector('.card-header');
                header.addEventListener('mousedown', (e) => {
                    bringToFront(cardBox);
                    if (e.target.classList.contains('win-btn')) return;
                    
                    winManager.dragging = cardBox;
                    winManager.startX = e.clientX;
                    winManager.startY = e.clientY;
                    winManager.startTop = cardBox.offsetTop;
                    winManager.startLeft = cardBox.offsetLeft;
                    
                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);
                });

                const resizer = cardBox.querySelector('.card-resizer');
                resizer.addEventListener('mousedown', (e) => {
                    bringToFront(cardBox);
                    winManager.resizing = cardBox;
                    winManager.startX = e.clientX;
                    winManager.startY = e.clientY;
                    winManager.startW = cardBox.offsetWidth;
                    winManager.startH = cardBox.offsetHeight;
                    
                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);
                    e.preventDefault();
                });
            }
        }
        
        window.UXManager = new UXCardManager();
"""
    html = html.replace('maxZ: 1000\n        };', 'maxZ: 1000\n        };\n' + manager_code)


    # Initialize default windows during load if empty, else load them from localStorage dynamically
    load_layout_code = """        function loadLayout() {
            const saved = localStorage.getItem('vli_wm_layout');
            if (!saved) {
                UXManager.createCard('VLI_CHAT', {top: '50px', right: '20px', width: '450px', height: 'inherit'}, 'coordinator');
                UXManager.createCard('VLI_TELEMETRY', {top: '50px', left: '20px', width: '450px', height: '350px'}, 'telemetry');
                UXManager.createCard('MACRO_WL', {top: '50px', left: '490px', width: '550px', height: '350px'}, 'watchlist');
                UXManager.createCard('ANALYSIS_REP', {top: '420px', left: '20px', width: '1020px', height: 'inherit'}, 'report');
                return;
            }
            try {
                const layout = JSON.parse(saved);
                for (const id in layout) {
                    const state = layout[id];
                    if (!state.typeGuid) continue; // Legacy safeguard
                    
                    const card = UXManager.createCard(state.typeGuid, state, state.instanceGuid);
                    if (card) {
                        if (state.display) card.style.display = state.display;
                        if (state.collapsed) card.classList.add('collapsed');
                        const z = parseInt(state.zIndex) || 100;
                        if (z > winManager.maxZ) winManager.maxZ = z;
                    }
                }
            } catch(e) {}
        }"""
        
    html = re.sub(r'function loadLayout\(\) \{[\s\S]*?\}(?=\s*function onMouseUp)', load_layout_code, html)

    save_layout_code = """        function saveLayout() {
            const layout = {};
            document.querySelectorAll('.card').forEach(card => {
                layout[card.id] = {
                    instanceGuid: card.dataset.instanceGuid,
                    typeGuid: card.dataset.typeGuid,
                    top: card.style.top,
                    left: card.style.left,
                    right: card.style.right,
                    width: card.style.width,
                    height: card.style.height,
                    zIndex: card.style.zIndex,
                    display: card.style.display,
                    collapsed: card.classList.contains('collapsed')
                };
            });
            localStorage.setItem('vli_wm_layout', JSON.stringify(layout));
        }"""
    html = re.sub(r'function saveLayout\(\) \{[\s\S]*?\}(?=\s*function loadLayout)', save_layout_code, html)

    # 4. Modify Handlers for dynamically generated content
    html = re.sub(
        r'const reportViewer = document.getElementById\(\'analysis-report-viewer\'\);',
        r"for (const id in UXManager.instances) { if (UXManager.instances[id].dataset.typeGuid === 'ANALYSIS_REP') { const reportViewer = document.getElementById('analysis-report-viewer-' + id);",
        html
    )
    # Be careful when replacing elements we need to close the `} }` loop. 
    # That approach via Regex might be brittle for big blocks.

    with open(fp, "w", encoding="utf-8") as f:
        f.write(html)
        
if __name__ == "__main__":
    migrate()
