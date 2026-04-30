
        let refreshCountdown = 60;
        let activeWin = null;
        let winManager = {
            dragging: null,
            resizing: null,
            startX: 0,
            startY: 0,
            startW: 0,
            startH: 0,
            startTop: 0,
            startLeft: 0,
            maxZ: 1000
        };

        // --- UX CARD FACTORY MANAGER ---
        const UX_CARD_LIMIT = 8;
        
        const CARD_TYPES = {
            'VLI_CHAT': { idPrefix: 'CI', title: 'Coordinator Interface', isSingleton: true },
            'VLI_TELEMETRY': { idPrefix: 'TM', title: 'Telemetry', isSingleton: true },
            'MACRO_WL': { idPrefix: 'WL', title: 'Macro Watchlist', isSingleton: false },
            'ANALYSIS_REP': { idPrefix: 'AR', title: 'Analysis Report', isSingleton: false }
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

                const liveBadgeHTML = (typeGuid === 'VLI_CHAT' || typeGuid === 'VLI_TELEMETRY') ? `<span class="live-badge" id="conn-status-${instanceGuid}">LIVE</span>` : '';
                
                let bodyContent = '';
                if (typeGuid === 'VLI_CHAT') {
                    bodyContent = `
                        <div class="card-body" style="padding:0; overflow:hidden; display:flex; flex-direction:column;">
                            <div class="chat-messages" id="chat-messages">
                                <div class="msg msg-ai"><strong>VLI</strong> initialized. Draggable Window Manager mode active.</div>
                            </div>
                            <div class="input-area">
                                <div class="gemini-panel">
                                    <textarea id="chat-input" placeholder="Enter directive..."></textarea>
                                    <div class="panel-controls">
                                        <div style="display:flex; align-items:center; gap:10px;">
                                            <div class="send-btn" id="send-stop-btn" onclick="handleSendStop()">➤</div>
                                        </div>
                                    </div>
                                </div>
                            </div>
                        </div>`;
                } else if (typeGuid === 'VLI_TELEMETRY') {
                    bodyContent = `<div class="card-body terminal telemetry-body-instance" id="telemetry-body-${instanceGuid}" data-guid="${instanceGuid}"></div>`;
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
                                <tbody class="macro-watchlist-body-instance" id="macro-watchlist-body-${instanceGuid}" data-guid="${instanceGuid}">
                                    <tr><td colspan="5" style="text-align:center; padding:20px;">Standby...</td></tr>
                                </tbody>
                            </table>
                        </div>`;
                } else if (typeGuid === 'ANALYSIS_REP') {
                    bodyContent = `
                        <div class="card-body terminal analysis-report-body analysis-report-viewer-instance" id="analysis-report-viewer-${instanceGuid}" data-guid="${instanceGuid}">
                            <div style="color:var(--text-muted); text-align:center; padding:40px;">No report active.</div>
                        </div>`;
                }

                cardBox.innerHTML = `
                    <div class="card-header">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <div class="descriptor" style="cursor: pointer; transition: transform 0.1s;" onclick="insertCardIdIntoChat('${badgeLabel}')" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'" title="Insert ${badgeLabel} to Chat">${badgeLabel}</div>
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
                    const inputElement = document.getElementById('chat-input');
                    if (inputElement) {
                        inputElement.addEventListener('keydown', handleChatInputKeyDown);
                    }
                }
                
                this.bindCardEvents(cardBox);
                return cardBox;
            }

            removeCard(instanceGuid) {
                const card = this.instances[instanceGuid];
                if (card) {
                    if (CARD_TYPES[card.dataset.typeGuid].isSingleton) {
                        card.style.display = 'none'; // Singleton preservation
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

        function insertCardIdIntoChat(badge) {
            const input = document.getElementById('chat-input');
            if (input) {
                const current = input.value;
                input.value = current + (current.length > 0 && !current.endsWith(' ') ? ' ' : '') + badge;
                input.focus();
            }
        }

        function bringToFront(el) {
            winManager.maxZ++;
            el.style.zIndex = winManager.maxZ;
        }

        function initWindowManager() {
            loadLayout();
            document.querySelectorAll('.card-header').forEach(header => {
                header.addEventListener('mousedown', (e) => {
                    const card = header.closest('.card');
                    bringToFront(card);
                    
                    if (e.target.classList.contains('win-btn')) return;
                    
                    winManager.dragging = card;
                    winManager.startX = e.clientX;
                    winManager.startY = e.clientY;
                    winManager.startTop = card.offsetTop;
                    winManager.startLeft = card.offsetLeft;
                    
                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);
                });
            });

            document.querySelectorAll('.card-resizer').forEach(resizer => {
                resizer.addEventListener('mousedown', (e) => {
                    const card = resizer.closest('.card');
                    bringToFront(card);
                    
                    winManager.resizing = card;
                    winManager.startX = e.clientX;
                    winManager.startY = e.clientY;
                    winManager.startW = card.offsetWidth;
                    winManager.startH = card.offsetHeight;
                    
                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);
                    e.preventDefault();
                });
            });
        }

        let snapModeEnabled = true;

        function toggleSnapMode() {
            snapModeEnabled = !snapModeEnabled;
            const statusEl = document.getElementById('menu-snap-status');
            if (statusEl) statusEl.innerText = snapModeEnabled ? "ON" : "OFF";
        }

        function onMouseMove(e) {
            if (winManager.dragging) {
                const dx = e.clientX - winManager.startX;
                const dy = e.clientY - winManager.startY;
                
                let newTop = winManager.startTop + dy;
                let newLeft = winManager.startLeft + dx;
                
                if (snapModeEnabled) {
                    const snapThreshold = 18; // Magnetic pulling distance
                    // When dragging, getBoundingClientRect won't have updated style yet, 
                    // but we can trust the computed new dimensions
                    const elWidth = winManager.dragging.offsetWidth;
                    const elHeight = winManager.dragging.offsetHeight;
                    
                    document.querySelectorAll('.card').forEach(other => {
                        if (other === winManager.dragging || other.style.display === 'none') return;
                        
                        const rect = other.getBoundingClientRect();
                        
                        // Vertical Snaps
                        if (Math.abs(newTop - rect.bottom) < snapThreshold) newTop = rect.bottom; // Snap to bottom edge
                        if (Math.abs(newTop + elHeight - rect.top) < snapThreshold) newTop = rect.top - elHeight; // Snap to top edge
                        if (Math.abs(newTop - rect.top) < snapThreshold) newTop = rect.top; // Align tops identically
                        
                        // Horizontal Snaps
                        if (Math.abs(newLeft - rect.right) < snapThreshold) newLeft = rect.right; // Snap to right edge
                        if (Math.abs(newLeft + elWidth - rect.left) < snapThreshold) newLeft = rect.left - elWidth; // Snap to left edge
                        if (Math.abs(newLeft - rect.left) < snapThreshold) newLeft = rect.left; // Align lefts identically
                    });
                }
                
                winManager.dragging.style.top = newTop + 'px';
                winManager.dragging.style.left = newLeft + 'px';
                winManager.dragging.style.right = 'auto'; 
                winManager.dragging.style.bottom = 'auto'; 
                winManager.dragging.style.margin = '0';
            }
            if (winManager.resizing) {
                const dx = e.clientX - winManager.startX;
                const dy = e.clientY - winManager.startY;
                winManager.resizing.style.width = (winManager.startW + dx) + 'px';
                winManager.resizing.style.height = (winManager.startH + dy) + 'px';
            }
        }

        function saveLayout() {
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
        }

        function loadWorkspace(customKey = null) {
            let targetKey = 'vli_wm_layout';
            if (!customKey) {
                const manual = prompt('Enter workspace name to load (leave blank for default):');
                if (manual) targetKey = 'vli_wm_layout_' + manual;
            } else {
                targetKey = customKey;
            }
            
            const saved = localStorage.getItem(targetKey);
            if (!saved) {
                if (targetKey === 'vli_wm_layout') {
                    // First boot - dynamic geometric fallback
                    UXManager.createCard('VLI_CHAT', {top: '50px', left: '20px', width: '450px', height: 'calc(100vh - 70px)'}, 'coordinator');
                    UXManager.createCard('MACRO_WL', {top: '50px', left: '490px', width: '700px', height: '400px'}, 'watchlist');
                    UXManager.createCard('VLI_TELEMETRY', {top: '50px', left: '1210px', width: 'calc(100vw - 1230px)', height: '400px'}, 'telemetry');
                    UXManager.createCard('ANALYSIS_REP', {top: '470px', left: '490px', width: 'calc(100vw - 510px)', height: 'calc(100vh - 490px)'}, 'report');
                } else {
                    alert('Workspace not found: ' + targetKey);
                }
                return;
            }
            try {
                // Clear existing
                Object.keys(UXManager.instances).forEach(id => {
                    const card = UXManager.instances[id];
                    if (card.dataset.typeGuid !== 'VLI_CHAT') {
                        card.remove();
                        delete UXManager.instances[id];
                    }
                });
                
                const layout = JSON.parse(saved);
                for (const id in layout) {
                    const state = layout[id];
                    if (!state.typeGuid) continue;
                    
                    const card = UXManager.createCard(state.typeGuid, state, state.instanceGuid);
                    if (card) {
                        if (state.display) card.style.display = state.display;
                        if (state.collapsed) card.classList.add('collapsed');
                        const z = parseInt(state.zIndex) || 100;
                        if (z > winManager.maxZ) winManager.maxZ = z;
                    }
                }
            } catch(e) {}
        }

        function loadLayout() {
            loadWorkspace('vli_wm_layout');
        }

        function saveWorkspaceAs() {
            const name = prompt('Enter workspace name to save:');
            if (name) {
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
                localStorage.setItem('vli_wm_layout_' + name, JSON.stringify(layout));
                alert('Workspace saved as: ' + name);
            }
        }

        function updateViewMenu() {
            const viewMenu = document.getElementById('view-menu-list');
            if(!viewMenu) return;
            viewMenu.innerHTML = '';
            
            const keys = Object.keys(UXManager.instances);
            if (keys.length === 0) {
                viewMenu.innerHTML = '<div class="dropdown-item" style="color:var(--text-muted); cursor:default;">No active windows</div>';
                return;
            }
            
            // Add a way to manually summon singletons if they are purely removed or never created
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'VLI_CHAT')) {
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="UXManager.createCard('VLI_CHAT')" style="color:var(--emerald-green);">[+] Spawn Coordinator</div>`;
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'VLI_TELEMETRY')) {
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="UXManager.createCard('VLI_TELEMETRY')" style="color:var(--emerald-green);">[+] Spawn Telemetry</div>`;
            }
            if (keys.length > 0) viewMenu.innerHTML += '<div class="dropdown-divider"></div>';

            keys.forEach(guid => {
                const card = UXManager.instances[guid];
                const badge = card.dataset.badge;
                const title = CARD_TYPES[card.dataset.typeGuid].title;
                const isVisible = card.style.display !== 'none';
                
                const check = isVisible ? '☑' : '☐';
                const el = document.createElement('div');
                el.className = 'dropdown-item';
                el.innerHTML = `<span>${title}</span> <span style="font-size:16px; margin-left: 20px;">${check}</span>`;
                el.onclick = () => {
                    if (isVisible) {
                        card.style.display = 'none';
                    } else {
                        card.style.display = '';
                        bringToFront(card);
                    }
                    saveLayout();
                    updateViewMenu();
                };
                viewMenu.appendChild(el);
            });
        }

        function onMouseUp() {
            if (winManager.dragging || winManager.resizing) {
                saveLayout();
            }
            winManager.dragging = null;
            winManager.resizing = null;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        }

        function toggleCollapse(id) {
            const el = document.getElementById(id);
            if (el.classList.contains('collapsed')) {
                el.classList.remove('collapsed');
                el.style.height = el.dataset.oldHeight || '350px';
            } else {
                el.dataset.oldHeight = el.style.height;
                el.classList.add('collapsed');
            }
            saveLayout();
        }

        function maxWin(id) {
            const el = document.getElementById(id);
            if (el.dataset.isMax === "true") {
                el.style.top = el.dataset.oldTop;
                el.style.left = el.dataset.oldLeft;
                el.style.width = el.dataset.oldWidth;
                el.style.height = el.dataset.oldHeight;
                el.dataset.isMax = "false";
            } else {
                el.dataset.oldTop = el.style.top;
                el.dataset.oldLeft = el.style.left;
                el.dataset.oldWidth = el.style.width;
                el.dataset.oldHeight = el.style.height;
                el.style.top = "0";
                el.style.left = "0";
                el.style.width = "100vw";
                el.style.height = "100vh";
                el.dataset.isMax = "true";
                bringToFront(el);
            }
        }

        function closeWin(id) {
            document.getElementById(id).style.display = 'none';
        }

        window.addEventListener('blur', onMouseUp);
        document.addEventListener('DOMContentLoaded', () => {
            initWindowManager();
            // --- VLI ORCHESTRA STANDALONE DETECTION ---
            if (popoutId) {
                console.log("[VLI_ORCHESTRA] Satellite Mode Active for:", popoutId);
                document.body.classList.add('standalone');
                const target = document.getElementById(popoutId);
                if (target) {
                    target.classList.add('popout-target');
                    target.style.position = 'static';
                    target.style.width = '100vw';
                    target.style.height = '100vh';
                }
                bc.onmessage = (e) => {
                    if (e.data.type === 'STATE_UPDATE') {
                        const data = e.data.state;
                        // Synchronize only the target card
                        if (popoutId === 'win-telemetry') renderTelemetry(data);
                        if (popoutId === 'win-watchlist') renderWatchlist(data);
                        if (popoutId === 'win-report') renderReport(data);
                        if (window.VLI_DEBUG) console.log("[VLI_ORCHESTRA] Satellite Node Re-Sync Successful.");
                    }
                };
            }
        });

        // --- VLI ORCHESTRA SPINE ---
        const bc = new BroadcastChannel('vli_spine');
        const urlParams = new URLSearchParams(window.location.search);
        const popoutId = urlParams.get('popout');

        function popoutWindow(id) {
            const width = 800;
            const height = 600;
            const left = (screen.width - width) / 2;
            const top = (screen.height - height) / 2;
            window.open(window.location.href.split('?')[0] + '?popout=' + id, id, 
                `width=${width},height=${height},top=${top},left=${left},toolbar=no,menubar=no,status=no`);
        }

        async function resetVLI() {
            const rtBtn = document.getElementById('rt-btn');
            rtBtn.style.color = 'var(--ruby-red)';
            rtBtn.innerText = '--';

            try {
                const response = await fetch('/api/vli/reset', { method: 'POST' });
                if (response.ok) {
                    document.getElementById('telemetry-body').innerHTML = '<div class="log-entry">SYSTEM_NODE: RESET SIGNAL SENT SUCCESSFULLY.</div>';
                    document.getElementById('telemetry-body').dataset.lastContent = ""; // Reset cache
                    document.getElementById('chat-messages').innerHTML = '';
                    document.getElementById('analysis-report-viewer').innerHTML = '<div style="display: flex; height: 100%; align-items: center; justify-content: center; color: var(--text-muted); font-family: Outfit; font-weight: 200; letter-spacing: 2px;">VLI_REPORT_STANDBY</div>';
                    document.getElementById('analysis-report-viewer').dataset.lastReport = "";
                    poll();
                }
            } catch (err) {
                console.error("VLI Reset Error:", err);
            } finally {
                setTimeout(() => {
                    rtBtn.style.color = '';
                    rtBtn.innerText = 'RT';
                }, 1000);
            }
        }

        function toggleDirectMode() {
            directMode = !directMode;
            const btn = document.getElementById('direct-mode-btn');
            const menuBtn = document.getElementById('menu-direct-status');
            if (btn) btn.classList.toggle('active', directMode);
            if (menuBtn) menuBtn.innerText = directMode ? "ON" : "OFF";
        }

        function toggleWindow(id) {
            const el = document.getElementById(id);
            if (el.style.display === 'none') {
                el.style.display = 'flex';
                bringToFront(el);
            } else {
                el.style.display = 'none';
            }
            saveLayout();
        }

        function resetLayout() {
            if (confirm("Reset Institutional Workspace to factory geometry?")) {
                localStorage.removeItem('vli_wm_layout');
                location.reload();
            }
        }

        function cascadeWindows() {
            const cards = document.querySelectorAll('.card');
            let offset = 60;
            cards.forEach((card, i) => {
                if (card.style.display !== 'none') {
                    card.style.top = offset + 'px';
                    card.style.left = offset + 'px';
                    bringToFront(card);
                    offset += 30;
                }
            });
            saveLayout();
        }

        function updateClock() {
            const clock = document.getElementById('system-clock');
            if (clock) {
                const now = new Date();
                clock.innerText = now.toLocaleTimeString('en-US', { hour12: false });
            }
        }
        setInterval(updateClock, 1000);
        updateClock();

        // --- WINDOWS HOTKEY ORCHESTRATION ---
        window.addEventListener('keydown', (e) => {
            if (e.altKey && !e.ctrlKey && !e.shiftKey) {
                const key = e.key;
                const winMap = {
                    '1': 'win-coordinator',
                    '2': 'win-telemetry',
                    '3': 'win-watchlist',
                    '4': 'win-report'
                };
                if (winMap[key]) {
                    e.preventDefault();
                    toggleWindow(winMap[key]);
                }
            }
        });

        let directMode = false;
        let lastVliThreadId = null;

        const sessionArtifacts = {};

        function openNativeNotepad(filename) {
            fetch('/api/vli/open-file', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ filename: filename })
            }).catch(e => console.error("Could not open native file:", e));
        }

        function renderArtifactToReport(event, artifactId) {
            if (event) event.preventDefault();
            const text = sessionArtifacts[artifactId];
            if (!text) return;

            // Find a blank report viewer or spawn a new one via the Factory
            let reportViewer = null;
            const viewers = document.querySelectorAll('.analysis-report-viewer-instance');
            for (const v of viewers) {
                if (v.innerText.includes("No report active.") || v.innerText.trim() === "") {
                    reportViewer = v;
                    break;
                }
            }
            if (!reportViewer) {
                const newCard = UXManager.createCard('ANALYSIS_REP');
                reportViewer = newCard.querySelector('.analysis-report-viewer-instance');
            }

            let formattedText = text;
            const t = text.trim();
            if (t.startsWith('{') || t.startsWith('[')) {
                try {
                    const parsed = JSON.parse(t);
                    formattedText = "```json\n" + JSON.stringify(parsed, null, 2) + "\n```";
                } catch (e) {
                    formattedText = "```json\n" + text + "\n```";
                }
            }

            reportViewer.innerHTML = `<div class="analysis-report">${applyStatusFormatting(marked.parse(formattedText))}</div>`;
            reportViewer.scrollTop = 0;
            // Bring the owning window to front
            bringToFront(reportViewer.closest('.card'));
            
            try {
                renderMathInElement(reportViewer, {
                    delimiters: [
                        { left: '$$', right: '$$', display: true },
                        { left: '$', right: '$', display: false },
                        { left: '\\(', right: '\\)', display: false },
                        { left: '\\[', right: '\\]', display: true }
                    ]
                });
            } catch (e) { }
        }

        function toggleDirectMode() {
            directMode = !directMode;
            const btn = document.getElementById('direct-mode-btn');
            const label = btn.querySelector('.label');
            if (!directMode) {
                btn.classList.remove('off');
                btn.classList.add('on');
                label.innerText = "COBALT AI: ON";
            } else {
                btn.classList.remove('on');
                btn.classList.add('off');
                label.innerText = "COBALT AI: OFF";
            }
        }

        let asyncMode = false;

        function toggleAsyncMode() {
            asyncMode = !asyncMode;
            const btn = document.getElementById('async-mode-btn');
            const label = btn.querySelector('.label');
            if (asyncMode) {
                btn.classList.remove('off');
                btn.classList.add('on');
                label.innerText = "ASYNC REPORT: ON";
            } else {
                btn.classList.remove('on');
                btn.classList.add('off');
                label.innerText = "ASYNC REPORT: OFF";
            }
        }

        window.sparklineAuditState = {}; // Store ground truth per ticker

        async function runSparklineAudit() {
            const btn = document.getElementById('verify-audit-btn');
            btn.innerText = "AUDITING...";
            btn.style.opacity = "0.5";
            btn.disabled = true;
            // [HARDENING] Reset audit state to prevent ghost dots from previous symbols
            window.sparklineAuditState = {};

            try {
                const tickers = Array.from(document.querySelectorAll('#macro-watchlist-body .symbol-bold'))
                    .map(td => td.dataset.ticker)
                    .filter(t => t && t !== "Awaiting Data");

                console.log("[VLI_AUDIT] Starting high-fidelity audit for tickers:", tickers);

                for (const ticker of tickers) {
                    // [PHASE_LOCK] pass the exact timestamp used for the current sparklines
                    const refTimeMs = (window.lastMacroUpdateTimestamp || 0) * 1000;
                    const prompt = `/vli get_sparkline_audit_vli --ticker=${ticker} --ref_time_ms=${refTimeMs} --DIRECT`;
                    const response = await fetch('/api/vli/action-plan', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({
                            text: prompt,
                            direct_mode: true,
                            vli_llm_type: "core"
                        })
                    });
                    const resData = await response.json();
                    if (resData.response) {
                        try {
                            // [HARDENING] Robust JSON extraction for narrative responses
                            const jsonMatch = resData.response.match(/\{[\s\S]*\}/);
                            if (jsonMatch) {
                                const audit = JSON.parse(jsonMatch[0].trim());
                                if (audit.points) {
                                    window.sparklineAuditState[ticker] = audit.points.map(p => p.price);

                                    // [TARGETED_REDRAW] Update the UI immediately for this ticker
                                    const row = document.querySelector(`#macro-watchlist-body tr td[data-ticker="${ticker}"]`)?.parentElement;
                                    if (row && window.currentMacroData && window.currentMacroData.macros) {
                                        const macro = window.currentMacroData.macros.find(m => m.ticker === ticker);
                                        if (macro && macro.sparkline && macro.sparkline.value) {
                                            const sparkTd = row.cells[row.cells.length - 1];
                                            sparkTd.innerHTML = drawSparkline(macro.sparkline.value, ticker);
                                            console.log(`[VLI_AUDIT] Targeted redraw successful for ${ticker}`);
                                        }
                                    }
                                }
                            }
                        } catch (e) { console.error("Parse Audit Error:", e, resData.response); }
                    }
                }
            } catch (err) {
                console.error("VLI Audit Error:", err);
            } finally {
                btn.innerText = "VERIFIED";
                btn.style.color = "var(--emerald-green)";
                btn.style.borderColor = "var(--emerald-green)";
                setTimeout(() => {
                    btn.innerText = "VERIFY";
                    btn.style.opacity = "1";
                    btn.style.color = "";
                    btn.style.borderColor = "";
                    btn.disabled = false;
                }, 3000);
            }
        }

        function drawSparkline(values, ticker = null) {
            if (!values || values.length < 2) return '';

            const validValues = values.filter(v => v !== null);
            if (validValues.length === 0) return '';

            const min = Math.min(...validValues);
            const max = Math.max(...validValues);
            const range = (max - min) || 1;
            const width = 64;
            const height = 16;

            const points = values.map((v, i) => {
                const x = (i / (values.length - 1)) * width;
                const y = v !== null ? height - ((v - min) / range) * height : null;
                return { x, y };
            });

            // Filter out null points for drawing
            const pathData = points.filter(p => p.y !== null).map((p, i) => {
                return `${i === 0 ? 'M' : 'L'} ${p.x},${p.y}`;
            }).join(' ');

            const isUp = validValues[validValues.length - 1] >= validValues[0];
            const color = isUp ? '#34d399' : '#fb7185';

            return `
                <div style="width: 64px; height: 16px; display: flex; align-items: center;">
                    <svg width="${width}" height="${height}" viewBox="0 0 ${width} ${height}" style="overflow:visible; display: block;" data-ticker="${ticker}">
                        <path d="${pathData}" fill="none" stroke="${color}" stroke-width="1.5" stroke-linecap="round" stroke-linejoin="round" style="filter: drop-shadow(0 0 4px ${color}66);" />
                    </svg>
                </div>
            `;
        }

        function updateCountdown() {
            refreshCountdown--;
            if (refreshCountdown < 0) refreshCountdown = 0;
            document.getElementById('macro-timer').innerText = `Refresh in: ${refreshCountdown}s`;
        }
        setInterval(updateCountdown, 1000);

        let isPolling = false;
        let isProcessing = false;
        async function poll() {
            if (isPolling) return;
            console.log("[VLI_TRACE] " + new Date().toLocaleTimeString() + " - Starting poll check...");
            isPolling = true;
            try {
                const res = await fetch('/api/vli/active-state');
                const data = await res.json();
                if (window.VLI_DEBUG) console.log("[VLI_TRACE] " + new Date().toLocaleTimeString() + " - Poll data received successfully.");
                if (data.error) throw new Error(data.error);

                document.getElementById('conn-status').innerText = "LIVE";
                document.getElementById('conn-status').style.color = "var(--emerald-green)";
                if (data.last_macro_update) {
                    window.lastMacroUpdateTimestamp = data.last_macro_update;
                    const lastUpdate = data.last_macro_update * 1000;
                    const now = Date.now();
                    const secondsPassed = Math.floor((now - lastUpdate) / 1000);
                    refreshCountdown = Math.max(0, 60 - (secondsPassed % 60));
                }

                // --- VLI ORCHESTRA: MASTER RENDER & BROADCAST ---
                renderMacros(data);
                renderWatchlist(data);
                renderTelemetry(data);
                renderReport(data);

                bc.postMessage({ type: 'STATE_UPDATE', state: data });
                if (window.VLI_DEBUG) console.log("[VLI_ORCHESTRA] Master Broadcast Sent.");

                // 4. Connectivity Status
                const statusBadge = document.getElementById('conn-status');
                statusBadge.innerText = "LIVE";
                statusBadge.style.color = "var(--emerald-green)";
                statusBadge.style.background = "rgba(63, 185, 80, 0.15)";

            } catch (e) {
                console.error("VLI Poll Error:", e);
                const statusBadge = document.getElementById('conn-status');
                if (statusBadge) {
                    statusBadge.innerText = "OFFLINE";
                    statusBadge.style.color = "var(--ruby-red)";
                    statusBadge.style.background = "rgba(248, 81, 73, 0.1)";
                }
            } finally {
                isPolling = false;
            }
        }

        // 1. Macros (Handled only if overview elements are present)
        function renderMacros(data) {
            const m1 = document.getElementById('macro-list-1');
            const m2 = document.getElementById('macro-list-2');
            if (data.macros && m1 && m2) {
                m1.innerHTML = ''; m2.innerHTML = '';
                data.macros.forEach((m, i) => {
                    const target = i < (data.macros.length / 2) ? m1 : m2;
                    const row = document.createElement('tr');
                    const price = m.price ? `$${parseFloat(m.price).toFixed(2)}` : '---';
                    const changeVal = (m.change !== undefined && m.change !== null) ? `${m.change >= 0 ? '+' : ''}${parseFloat(m.change).toFixed(2)}%` : '---';
                    const color = m.color || (m.change >= 0 ? 'var(--price-up)' : 'var(--price-down)');

                    row.innerHTML = `
                        <td class="symbol-bold">${m.symbol}</td>
                        <td class="val-mono" style="font-weight:400;">${price}</td>
                        <td class="val-mono" style="color:${color}; font-weight:400;">${changeVal}</td>
                    `;
                    target.appendChild(row);
                });
            }
        }

        // 1b. Macro Watchlist Content (Structural JSON Support)
        function renderWatchlist(data) {
            if (!data.macro_watchlist_content) return;
            const mw = data.macro_watchlist_content;
            if (!(mw.type === 'table' && mw.rows)) return;
            if (!window.lastMacroWatchlistState) window.lastMacroWatchlistState = {};

            document.querySelectorAll('.macro-watchlist-body-instance').forEach(tbody => {
                const instanceGuid = tbody.dataset.guid;
                tbody.innerHTML = '';
            
                mw.rows.forEach(row => {
                    const label = row[0];
                    const ticker = row[1];
                    const priceDisplay = row[2];
                    const changeObj = row[3];
                    const sortino = row[4];
                    const sparklineObj = row[5];

                    const priceNum = parseFloat(priceDisplay.replace(/[$,%]/g, ''));
                    const pctChange = changeObj.value;

                    let sortinoColor = '#ff4444';
                    if (sortino >= 2.0) sortinoColor = '#00ff88';
                    else if (sortino >= 1.0) sortinoColor = '#ff9900';

                    let color = '#fff';
                    if (window.lastMacroWatchlistState[ticker]) {
                        const lastPrice = window.lastMacroWatchlistState[ticker].price;
                        if (priceNum > lastPrice) color = 'var(--price-up)';
                        else if (priceNum < lastPrice) color = 'var(--price-down)';
                    }
                    
                    const tr = document.createElement('tr');
                    tr.style.fontSize = '14px';
                    tr.innerHTML = `
                        <td class="symbol-bold" style="padding: 6px 0; vertical-align: middle; max-width: 110px;" data-ticker="${ticker}">
                            <div style="font-size: 11px; color: var(--text-muted); line-height: 1; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${label}</div>
                            <div style="line-height: 1;">${ticker}</div>
                        </td>
                        <td class="val-mono" style="color: ${color}; transition: color 0.5s ease; padding: 6px 0; vertical-align: middle;">${priceDisplay}</td>
                        <td class="val-mono" style="color: ${pctChange >= 0 ? 'var(--price-up)' : 'var(--price-down)'}; padding: 6px 0; vertical-align: middle;">
                            ${pctChange >= 0 ? '▲' : '▼'} ${Math.abs(pctChange).toFixed(2)}%
                        </td>
                        <td class="val-mono" style="color: ${sortinoColor}; font-weight: 700; padding: 6px 0; vertical-align: middle;">${sortino}</td>
                        <td style="padding: 6px 0; vertical-align: middle;">${drawSparkline(sparklineObj.value, ticker)}</td>
                    `;
                    tbody.appendChild(tr);
                });
            });
            
            // Only update tracker state once per broadcast to avoid duplicate overrides in multi-instance environments
            if (mw.rows.length > 0) {
                 mw.rows.forEach(row => {
                     const priceNum = parseFloat(row[2].replace(/[$,%]/g, ''));
                     window.lastMacroWatchlistState[row[1]] = { price: priceNum };
                 });
            }
        }

        // 2. Telemetry
        function renderTelemetry(data) {
            document.querySelectorAll('.telemetry-body-instance').forEach(tBody => {
                const logContainer = tBody.closest('.terminal');
                const wasAtBottom = logContainer.scrollHeight - logContainer.scrollTop <= logContainer.clientHeight + 50;

                const newTelemetry = data.telemetry_tail || "";
                if (tBody.dataset.lastContent !== newTelemetry) {
                    let safeTelemetry = newTelemetry;
                    const leakKeywords = ["# SECURITY OVERRIDE", "APEX 500 SYSTEM", "USER IDENTITY: DAVE", "OPERATIONAL MANDATE"];
                    if (leakKeywords.some(k => safeTelemetry.toUpperCase().includes(k))) {
                        safeTelemetry = "**⚠️ [VLI_MONITOR]: TECHNICAL STATE LEAKAGE SUPPRESSED.**";
                    }
                    tBody.innerHTML = marked.parse(safeTelemetry);
                    tBody.dataset.lastContent = safeTelemetry;

                    if (wasAtBottom) {
                        logContainer.scrollTo({ top: logContainer.scrollHeight, behavior: 'smooth' });
                    }
                }
            });
        }

        // 3. Reports
        function renderReport(data) {
            document.querySelectorAll('.analysis-report-viewer-instance').forEach(reportViewer => {
                if (data.async_report && reportViewer.dataset.lastReport !== data.async_report) {
                    let safeReport = data.async_report;
                    const leakKeywords = ["# SECURITY OVERRIDE", "APEX 500 SYSTEM", "USER IDENTITY: DAVE", "OPERATIONAL MANDATE"];
                    if (leakKeywords.some(k => safeReport.toUpperCase().includes(k))) {
                        reportViewer.dataset.lastReport = data.async_report;
                    } else {
                        reportViewer.innerHTML = `<div class="analysis-report">${applyStatusFormatting(marked.parse(safeReport))}</div>`;
                        reportViewer.dataset.lastReport = data.async_report;
                        reportViewer.scrollTop = 0;
                        try {
                            renderMathInElement(reportViewer, {
                                delimiters: [
                                    { left: '$$', right: '$$', display: true },
                                    { left: '$', right: '$', display: false },
                                    { left: '\\(', right: '\\)', display: false },
                                    { left: '\\[', right: '\\]', display: true }
                                ]
                            });
                        } catch (e) { }
                    }
                }
            });
        }



        let activeTypingIndicator = null;

        function showTypingIndicator() {
            const msgBox = document.getElementById('chat-messages');
            if (activeTypingIndicator) return;

            activeTypingIndicator = document.createElement('div');
            activeTypingIndicator.className = 'typing-indicator';
            activeTypingIndicator.innerHTML = `
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
                <div class="typing-dot"></div>
            `;
            msgBox.appendChild(activeTypingIndicator);
            msgBox.scrollTop = msgBox.scrollHeight;
        }

        function hideTypingIndicator() {
            if (activeTypingIndicator) {
                activeTypingIndicator.remove();
                activeTypingIndicator = null;
            }
        }

        async function handleSendStop() {
            if (isProcessing) {
                await stopMessage();
            } else {
                await sendMessage();
            }
        }

        async function stopMessage() {
            try {
                const btn = document.getElementById('send-stop-btn');
                btn.innerText = "➤";
                btn.classList.remove('processing');
                isProcessing = false;
                hideTypingIndicator();

                await fetch('/api/vli/reset', { method: 'POST' });
                const msgBox = document.getElementById('chat-messages');
                const sysMsg = document.createElement('div');
                sysMsg.className = 'msg msg-ai';
                sysMsg.style.borderColor = 'var(--ruby-red)';
                sysMsg.innerHTML = "<strong>SYSTEM:</strong> Processing terminated. Agent state reset to safe baseline.";
                msgBox.appendChild(sysMsg);
                msgBox.scrollTop = msgBox.scrollHeight;
            } catch (e) { }
        }

        function applyStatusFormatting(html) {
            // Wrap in span to ensure all text nodes are bracketed by > and <
            let processed = `<span>${html}</span>`;

            processed = processed.replace(/>([^<]+)</g, (match, innerText) => {
                let text = innerText;

                // Color values: +val (Dark Green), -val (Dark Red), val (White)
                text = text.replace(/(^|\s|\[|\()([+-]?)(\$?\d+(?:,\d+)*(?:\.\d+)?(?:[kKmMbBtT%])?)(?=[.,;!?\])]*(?:\s|$))/g, (m, prefix, sign, val) => {
                    let color = '#ffffff'; // bold white default
                    if (sign === '+') {
                        color = '#2ea043'; // darker green
                    } else if (sign === '-') {
                        color = '#d73a49'; // darker red
                    }
                    return `${prefix}<span style="color: ${color}; font-weight: 400;">${sign}${val}</span>`;
                });

                // Status Keywords
                text = text.replace(/\b(HALT|DENIED|STOP|REJECTED|ABORT|FAILED)\b/g, '<span style="color: var(--ruby-red); font-weight: 400;">$&</span>');
                text = text.replace(/\b(WAIT|HOLD|PENDING|WARNING)\b/g, '<span style="color: var(--amber-gold); font-weight: 400;">$&</span>');
                text = text.replace(/\b(APPROVED|PROCEED|AUTHORIZE|GO|SUCCESS|RESOLVED|PASSED)\b/g, '<span style="color: var(--emerald-green); font-weight: 400;">$&</span>');

                // Card Badge Designator Shortcut highlighting (CI, TM, WL, AR)
                text = text.replace(/\b(CI|TM\d*|WL\d*|AR\d*)\b/g, '<span style="color: var(--cobalt-blue); font-weight: 700;">$&</span>');

                return `>${text}<`;
            });

            // Remove the wrapping <span></span> (6 chars at start, 7 chars at end)
            return processed.slice(6, -7);
        }

        async function submitFeedback(event, vote) {
            const btn = event.currentTarget;
            if (btn.dataset.submitted) return;
            
            const aiMsg = btn.closest('.msg-ai');
            if (!aiMsg || !aiMsg.dataset.requestText) return;

            const reqText = aiMsg.dataset.requestText;
            
            let respText = "";
            const inlineContainer = aiMsg.querySelector('.chat-inline-markdown');
            if (inlineContainer) respText = inlineContainer.innerText;
            else respText = aiMsg.innerText;

            btn.style.color = (vote === 'up') ? 'var(--emerald-green)' : 'var(--ruby-red)';
            btn.dataset.submitted = 'true';
            btn.title = 'Syncing...';

            try {
                const res = await fetch('/api/v1/vli/feedback', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ vote: vote, request: reqText, response: respText })
                });
                if (res.ok) {
                     btn.title = (vote === 'up') ? 'Positive Feedback Logged' : 'Negative Feedback Logged';
                } else {
                     btn.title = 'Error logging feedback';
                     btn.style.color = 'var(--amber-gold)';
                }
            } catch(e) {
                 btn.title = 'Network error logger';
                 btn.style.color = 'var(--text-muted)';
            }
        }

        async function regenerateMessage(event) {
            const btn = event.currentTarget;
            const aiMsg = btn.closest('.msg-ai');
            if (aiMsg && aiMsg.dataset.requestText) {
                // If the system is currently processing something else, ignore
                if (isProcessing) return;
                sendMessage(aiMsg);
            }
        }

        async function sendMessage(regenTargetAiMsg = null) {
            const input = document.getElementById('chat-input');
            const isRegen = !!regenTargetAiMsg;
            const rawText = isRegen ? regenTargetAiMsg.dataset.requestText : input.value.trim();
            if (!rawText) return;

            const msgBox = document.getElementById('chat-messages');

            if (!isRegen) {
                // Push to history
                chatHistory.push(rawText);
                historyIndex = chatHistory.length;
                input.value = '';

                const userMsg = document.createElement('div');
                userMsg.className = 'msg msg-user';
                userMsg.innerHTML = applyStatusFormatting(marked.parse(rawText));
                msgBox.appendChild(userMsg);

                // Render Math for the user message
                renderMathInElement(userMsg, {
                    delimiters: [
                        { left: '$$', right: '$$', display: true },
                        { left: '$', right: '$', display: false },
                        { left: '\\(', right: '\\)', display: false },
                        { left: '\\[', right: '\\]', display: true }
                    ]
                });
                msgBox.scrollTop = msgBox.scrollHeight;
            }

            const btn = document.getElementById('send-stop-btn');
            btn.innerText = "";
            btn.classList.add('processing');
            isProcessing = true;

            if (!isRegen) {
                showTypingIndicator();
            } else {
                regenTargetAiMsg.innerHTML = '<div class="typing-indicator" style="padding: 10px 0;"><span>.</span><span>.</span><span>.</span></div>';
            }

            // Render Math for the user message
            renderMathInElement(userMsg, {
                delimiters: [
                    { left: '$$', right: '$$', display: true },
                    { left: '$', right: '$', display: false },
                    { left: '\\(', right: '\\)', display: false },
                    { left: '\\[', right: '\\]', display: true }
                ]
            });
            msgBox.scrollTop = msgBox.scrollHeight;

            try {
                let requestText = rawText;

                if (requestText.toUpperCase().startsWith("REFRESH")) {
                    let targetCard = requestText.substring(7).trim().toUpperCase();
                    if (!targetCard) targetCard = "ALL";
                    console.log("[VLI_TRACE] " + new Date().toLocaleTimeString() + " - Intercepting UX refresh command for: " + targetCard);


                    fetch('/api/vli/refresh-card', {
                        method: 'POST',
                        headers: { 'Content-Type': 'application/json' },
                        body: JSON.stringify({ card_id: targetCard })
                    });

                    btn.classList.remove('processing');
                    btn.innerText = "➤";
                    isProcessing = false;
                    return;
                }

                let rawDataMode = false;
                if (text.toUpperCase().includes("--RAW") || (text.toUpperCase().includes("RAW") && (text.toUpperCase().includes("SMC") || text.toUpperCase().includes("DATA")))) {
                    rawDataMode = true;
                    requestText = text.replace(/--raw/ig, "").trim();
                }

                console.log("[VLI_TRACE] " + new Date().toLocaleTimeString() + " - Submitting command to backend: " + requestText);
                const startTime = performance.now();
                const res = await fetch('/api/vli/action-plan', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        text: requestText,
                        direct_mode: directMode,
                        raw_data_mode: rawDataMode,
                        background_synthesis: asyncMode,
                        thread_id: lastVliThreadId
                    })
                });
                const data = await res.json();
                if (data.thread_id) {
                    lastVliThreadId = data.thread_id;
                    console.log("[VLI_TRACE] Session thread pinned: " + lastVliThreadId);
                }
                const durationSec = ((performance.now() - startTime) / 1000).toFixed(2);
                console.log("[VLI_TRACE] " + new Date().toLocaleTimeString() + ` - Command response received in ${durationSec}s.`);
                
                hideTypingIndicator();

                if (isProcessing) {
                    const aiMsg = isRegen ? regenTargetAiMsg : document.createElement('div');
                    if (!isRegen) aiMsg.className = 'msg msg-ai';
                    aiMsg.dataset.requestText = rawText;
                    
                    const responseText = data.response || "No response generated.";

                    if (rawDataMode) {
                        try {
                            const blob = new Blob([responseText], { type: 'application/json' });
                            const url = URL.createObjectURL(blob);
                            const artifactId = 'artifact_' + Date.now() + Math.floor(Math.random() * 1000);
                            sessionArtifacts[artifactId] = responseText;
                            aiMsg.innerHTML = `<strong>[HEADLESS DATA ENGINE - RAW JSON]:</strong><br>Returned <a href="${url}" download="vli_raw_payload.json" onclick="renderArtifactToReport(event, '${artifactId}')" ondblclick="openNativeNotepad('vli_raw_payload.json')" style="color: #e5e7eb; font-weight: 700; text-decoration: underline; background: rgba(128, 128, 128, 0.25); padding: 4px 8px; border-radius: 4px; display: inline-block; margin-top: 10px; cursor: pointer;">vli_raw_payload.json</a><div style="font-size:10px; color:var(--text-muted); margin-top:8px;">⏱️ Latency: ${durationSec}s</div>`;
                        } catch (e) {
                            aiMsg.innerHTML = `<strong>[HEADLESS DATA ENGINE - RAW JSON]:</strong> Data array returned successfully.<div style="font-size:10px; color:var(--text-muted); margin-top:8px;">⏱️ Latency: ${durationSec}s</div>`;
                        }
                    } else {
                        const leakKeywords = ["# SECURITY OVERRIDE", "APEX 500 SYSTEM", "USER IDENTITY: DAVE", "OPERATIONAL MANDATE", "QUOTA LIMIT", "RESOURCE_EXHAUSTED", "RATE_LIMIT", "QUOTA_EXHAUSTED"];
                        let cleanText = responseText;
                        const isLeak = leakKeywords.some(k => cleanText.toUpperCase().includes(k)) || cleanText.toUpperCase().includes("STRUCTURAL_EXCEPTION") || cleanText.includes("Integrity check failed");
                        const isQuota = cleanText.toUpperCase().includes("QUOTA_EXHAUSTED") || cleanText.toUpperCase().includes("RESOURCE_EXHAUSTED") || cleanText.toUpperCase().includes("RATE_LIMIT");
                        const isFallback = isLeak || isQuota || cleanText.toUpperCase().includes("INSTITUTIONAL PROCESSING RECOVERY");

                        // [SECURITY] Catch Fallback Message
                        if (isFallback) {
                            const warnMsg = document.createElement('div');
                            warnMsg.className = 'msg msg-ai';
                            warnMsg.style.borderLeftColor = isQuota ? '#ff9d00' : '#fdbd33';

                            let matchedModel = "Gemini 3 Pro";
                            const match = cleanText.match(/(?:Quota limit reached for|Tier .*? failed).*?([a-z0-9.-]*?gemini-[a-z0-9.-]+)/i);
                            if (match) {
                                matchedModel = match[1].replace(/[()]/g, '').trim();
                                if (matchedModel.includes("gemini-3")) matchedModel = matchedModel.includes("pro") ? "Gemini 3 Pro" : "Gemini 3 Flash";
                            } else if (cleanText.includes("gemini-3-pro")) {
                                matchedModel = "Gemini 3 Pro";
                            } else if (cleanText.includes("gemini-3-flash") || cleanText.includes("basic")) {
                                matchedModel = "Gemini 3 Flash";
                            }

                            const errorType = isQuota ? "API Quota Limit Reached" : "Structural Exception Detected";
                            const errorDetail = isQuota ? "throtled" : "generated a payload that violated internal security schemas";

                            warnMsg.innerHTML = `<span style="color: ${isQuota ? '#ff9d00' : '#fdbd33'}; font-weight: normal;">⚠️ <strong>${errorType}:</strong> <span style="color: white; font-family: 'Courier New', Courier, monospace; font-weight: bold;">${matchedModel}</span> ${errorDetail}. Managed recovery active.</span>`;
                            msgBox.appendChild(warnMsg);

                            // Strip internal fallback wrapper from the response if present 
                            const preIdx = cleanText.lastIndexOf("Falling back to");
                            if (preIdx !== -1) {
                                let startAnalysis = cleanText.indexOf("\n", preIdx);
                                if (startAnalysis !== -1) {
                                    cleanText = cleanText.substring(startAnalysis).trim();
                                }
                            }

                            // Stop if it was an unrecoverable leak
                            if (leakKeywords.some(k => cleanText.toUpperCase().includes(k)) && !cleanText.toUpperCase().includes("STRUCTURAL_EXCEPTION")) {
                                msgBox.scrollTop = msgBox.scrollHeight;
                                return;
                            }

                            // [NEW] Inject persistent warning at the top of the generated report
                            const fallbackLabel = isQuota ? "Quota limits" : "structural integrity checks";
                            cleanText = `<div style="border-left: 4px solid var(--amber-gold); padding: 12px 16px; margin-bottom: 20px; background: rgba(210, 153, 34, 0.08); border-radius: 4px;"><span style="color: var(--amber-gold); font-weight: normal;">⚠️ <strong>Fallback Mode Active:</strong> Due to ${fallbackLabel}, this analysis was generated by a lower-tier model. The accuracy and depth of results may be compromised.</span></div>\n\n` + cleanText;
                        }

                        // [UX_REFINEMENT] Detect short vs long responses
                        // A short response is a single paragraph without structural Markdown headers, tables, or lists.
                        const isShort = !cleanText.includes('###') &&
                            !cleanText.includes('|') &&
                            !cleanText.includes('\n* ') &&
                            !cleanText.includes('\n- ') &&
                            cleanText.trim().split(/\n\s*\n/).length <= 1 &&
                            cleanText.length < 600;

                        if (!isShort) {
                            const artifactId = 'artifact_' + Date.now() + Math.floor(Math.random() * 1000);
                            sessionArtifacts[artifactId] = cleanText;

                            // Inline Rendering in Chat Log with Gemini-style footer
                            const footerHTML = `
                                <div class="gemini-footer" style="display:flex; align-items:center; gap: 14px; margin-top: 15px; color: var(--text-muted); padding-top: 10px; border-top: 1px solid rgba(255,255,255,0.05); font-size:14px; user-select:none;">
                                    <div style="cursor:default;" title="Latency: ${durationSec}s">◷ ${durationSec}s</div>
                                    <div style="cursor:pointer; transition:color 0.2s;" onclick="submitFeedback(event, 'up')" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="Good Response"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:-2px;"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg></div>
                                    <div style="cursor:pointer; transition:color 0.2s;" onclick="submitFeedback(event, 'down')" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="Bad Response"><svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:-2px;"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path></svg></div>
                                    <div style="cursor:pointer; transition:color 0.2s;" onclick="regenerateMessage(event)" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="Regenerate">⟳</div>
                                    <div style="cursor:pointer; transition:color 0.2s;" onclick="navigator.clipboard.writeText(sessionArtifacts['${artifactId}'])" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="Copy Raw Markdown">⎘</div>
                                    <div style="cursor:pointer; transition:color 0.2s;" onclick="renderArtifactToReport(event, '${artifactId}')" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="Popout to Analysis Window">⧉</div>
                                    <div style="cursor:pointer; transition:color 0.2s;" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="More Actions">⋮</div>
                                </div>`;
                                
                            aiMsg.innerHTML = `<div class="chat-inline-markdown">${applyStatusFormatting(marked.parse(cleanText))}</div>` + footerHTML;
                        } else {
                            // Inline rendering for single-paragraph responses
                            aiMsg.innerHTML = `<div class="chat-inline-markdown">${applyStatusFormatting(marked.parse(cleanText))}</div>` + `<div style="font-size:10px; color:var(--text-muted); margin-top:8px; display:flex; gap:10px; align-items:center;"><span>◷ Latency: ${durationSec}s</span><span style="cursor:pointer; transition:color 0.2s;" onclick="submitFeedback(event, 'up')" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="Good Response"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:-2px;"><path d="M14 9V5a3 3 0 0 0-3-3l-4 9v11h11.28a2 2 0 0 0 2-1.7l1.38-9a2 2 0 0 0-2-2.3zM7 22H4a2 2 0 0 1-2-2v-7a2 2 0 0 1 2-2h3"></path></svg></span><span style="cursor:pointer; transition:color 0.2s;" onclick="submitFeedback(event, 'down')" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="Bad Response"><svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-bottom:-2px;"><path d="M10 15v4a3 3 0 0 0 3 3l4-9V2H5.72a2 2 0 0 0-2 1.7l-1.38 9a2 2 0 0 0 2 2.3zm7-13h2.67A2.31 2.31 0 0 1 22 4v7a2.31 2.31 0 0 1-2.33 2H17"></path></svg></span><span style="cursor:pointer; transition:color 0.2s;" onclick="regenerateMessage(event)" onmouseover="this.style.color='#fff'" onmouseout="this.style.color='var(--text-muted)'" title="Regenerate">⟳</span></div>`;
                        }
                    } // close else

                    if (!isRegen) msgBox.appendChild(aiMsg);

                    // Render Math for the AI message response
                    renderMathInElement(aiMsg, {
                        delimiters: [
                            { left: '$$', right: '$$', display: true },
                            { left: '$', right: '$', display: false },
                            { left: '\\(', right: '\\)', display: false },
                            { left: '\\[', right: '\\]', display: true }
                        ]
                    });

                    msgBox.scrollTop = msgBox.scrollHeight;
                }
            } catch (e) {
                if (isProcessing) {
                    const errMsg = document.createElement('div');
                    errMsg.className = 'msg msg-ai';
                    errMsg.style.borderColor = 'var(--ruby-red)';
                    errMsg.innerHTML = "<strong>ERROR:</strong> Directive routing failed. Remote service unreachable.";
                    msgBox.appendChild(errMsg);
                }
            } finally {
                hideTypingIndicator();
                btn.innerText = "➤";
                btn.classList.remove('processing');
                isProcessing = false;
            }
        }

        // [V10.4] Synchronization with Background Scraper
        (async () => {
            const macroCard = document.querySelector('.card[style*="display: none"]');
            const state = macroCard ? "off" : "on";
            try {
                await fetch(`/api/vli/macro/toggle/${state}`, { method: 'POST' });
            } catch (e) { }
        })();

        // --- TRADER PROFILE LOGIC ---
        let profileState = {
            active_persona: '', active_strategy: '', active_rules: '',
            persona_files: [], strategy_files: [], rules_files: [],
            persona_content: '', strategy_content: '', rules_content: ''
        };
        let activeProfileTab = 'persona';

        async function openTraderProfile() {
            document.getElementById('profile-modal').style.display = 'flex';
            document.getElementById('profile-status').innerText = 'Syncing...';
            try {
                const res = await fetch('/api/v1/trader-profile');
                if(res.ok) {
                    const data = await res.json();
                    profileState = {
                        active_persona: data.active_persona,
                        active_strategy: data.active_strategy,
                        active_rules: data.active_rules,
                        persona_files: data.persona_files,
                        strategy_files: data.strategy_files,
                        rules_files: data.rules_files,
                        persona_content: data.persona,
                        strategy_content: data.strategy,
                        rules_content: data.rules
                    };
                    document.getElementById('profile-status').innerText = 'Synced Configurations.';
                    activeProfileTab = ''; // Prevent initial state clobber
                    switchProfileTab('persona');
                } else {
                    document.getElementById('profile-status').innerText = 'Failed to load';
                }
            } catch(e) {
                document.getElementById('profile-status').innerText = 'Network error';
            }
        }

        function closeTraderProfile() {
            document.getElementById('profile-modal').style.display = 'none';
        }

        function switchProfileTab(tab) {
            const ta = document.getElementById('profile-editor');
            const selector = document.getElementById('profile-selector');
            
            if (activeProfileTab && profileState[activeProfileTab + '_content'] !== undefined && ta.value !== 'Loading...') {
                 profileState[activeProfileTab + '_content'] = ta.value;
                 if (selector.value) profileState['active_' + activeProfileTab] = selector.value;
            }

            activeProfileTab = tab;
            ta.value = profileState[tab + '_content'] || '';
            
            // Populate Dropdown
            selector.innerHTML = '';
            const fileList = profileState[tab + '_files'] || [];
            fileList.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f;
                opt.innerText = f;
                if (f === profileState['active_' + tab]) opt.selected = true;
                selector.appendChild(opt);
            });

            ['persona', 'strategy', 'rules'].forEach(t => {
                const btn = document.getElementById('tab-btn-' + t);
                if (t === tab) btn.classList.add('active');
                else btn.classList.remove('active');
            });
        }
        
        async function onProfileDropdownChange() {
            const selector = document.getElementById('profile-selector');
            const targetFile = selector.value;
            profileState['active_' + activeProfileTab] = targetFile;
            
            document.getElementById('profile-status').innerText = 'Loading module...';
            try {
                const res = await fetch('/api/v1/trader-profile/file?name=' + encodeURIComponent(targetFile));
                if (res.ok) {
                    const data = await res.json();
                    document.getElementById('profile-editor').value = data.content;
                    profileState[activeProfileTab + '_content'] = data.content;
                    document.getElementById('profile-status').innerText = 'Loaded module successfully.';
                }
            } catch(e) { }
        }

        async function addNewProfileFile() {
             const name = prompt("Enter a simple name for the new module (e.g. 'momentum', 'swing'):");
             if (!name) return;
             
             document.getElementById('profile-status').innerText = 'Creating module...';
             try {
                 const res = await fetch('/api/v1/trader-profile/new', {
                     method: 'POST',
                     headers: {'Content-Type': 'application/json'},
                     body: JSON.stringify({ type: activeProfileTab, name: name })
                 });
                 if (res.ok) {
                     const data = await res.json();
                     profileState[activeProfileTab + '_files'].push(data.filename);
                     profileState['active_' + activeProfileTab] = data.filename;
                     
                     switchProfileTab(activeProfileTab);
                     onProfileDropdownChange();
                 } else {
                     document.getElementById('profile-status').innerText = 'Failed to create module.';
                 }
             } catch(e) {}
        }
        
        async function resetCurrentProfileTab() {
            document.getElementById('profile-status').innerText = 'Resetting module...';
            try {
                const selector = document.getElementById('profile-selector');
                const targetFile = selector.value;
                const res = await fetch('/api/v1/trader-profile/file?name=' + encodeURIComponent(targetFile));
                if (res.ok) {
                    const data = await res.json();
                    document.getElementById('profile-editor').value = data.content;
                    profileState[activeProfileTab + '_content'] = data.content;
                    document.getElementById('profile-status').innerText = 'Discarded unsaved changes.';
                }
            } catch(e) { }
        }

        async function saveTraderProfile() {
            const ta = document.getElementById('profile-editor');
            const selector = document.getElementById('profile-selector');
            profileState[activeProfileTab + '_content'] = ta.value;
            if (selector.value) profileState['active_' + activeProfileTab] = selector.value;

            document.getElementById('profile-status').innerText = 'Saving...';
            try {
                const res = await fetch('/api/v1/trader-profile', {
                    method: 'POST',
                    headers: {'Content-Type':'application/json'},
                    body: JSON.stringify(profileState)
                });
                if(res.ok) {
                    document.getElementById('profile-status').innerText = '✔ Backup created & Config saved successfully.';
                    setTimeout(closeTraderProfile, 1500);
                } else {
                    document.getElementById('profile-status').innerText = 'Failed to save';
                }
            } catch(e) {
                document.getElementById('profile-status').innerText = 'Network error saving config';
            }
        }

        setInterval(poll, 5000);

        // Bootstrap on successful DOM load
        document.addEventListener("DOMContentLoaded", () => {
            loadLayout(); // Guarantee UX configurations recall on reload
            poll();
            
            // Re-bind access keys globally so typical OS combo intercepts work outside form focus
            document.addEventListener('keydown', function(e) {
                if(e.altKey && !e.ctrlKey) {
                    if(e.key.toLowerCase() === 'f') {
                        document.querySelector('[accesskey="f"]').click();
                    } else if (e.key.toLowerCase() === 'v') {
                        document.querySelector('[accesskey="v"]').focus();
                        // For pure css hover, native trigger is slightly hard via JS, so rely on hover.
                    }
                }
            });

            // Initialize Modal Dragging Hook
            const modHeader = document.querySelector('.modal-header');
            const modContent = document.querySelector('.modal-content');
            let isModDragging = false, mStartX, mStartY, mInitX, mInitY;
            modHeader.addEventListener('mousedown', (e) => {
                if(e.target.closest('div[onclick]')) return;
                isModDragging = true;
                mStartX = e.clientX;
                mStartY = e.clientY;
                mInitX = modContent.offsetLeft;
                mInitY = modContent.offsetTop;
            });
            document.addEventListener('mousemove', (e) => {
                if(!isModDragging) return;
                const dx = e.clientX - mStartX;
                const dy = e.clientY - mStartY;
                modContent.style.left = (mInitX + dx) + 'px';
                modContent.style.top = (mInitY + dy) + 'px';
            });
            document.addEventListener('mouseup', () => { isModDragging = false; });
        });

        // [STABILITY] Force-inject the VERIFY button if the header was overwritten
        setTimeout(() => {
            const header = document.querySelector('.card-header:contains("MACRO WATCHLIST")') || document.querySelector('.card:nth-child(2) .card-header');
            if (header && !document.getElementById('verify-audit-btn')) {
                const btnContainer = document.createElement('div');
                btnContainer.style.display = 'flex';
                btnContainer.style.alignItems = 'center';
                btnContainer.style.gap = '8px';
                btnContainer.innerHTML = `
                    <button id="verify-audit-btn" onclick="runSparklineAudit()" 
                            style="background: rgba(88, 166, 255, 0.1); border: 1px solid rgba(88, 166, 255, 0.4); 
                            color: var(--cobalt-blue); font-size: 9px; padding: 2px 6px; border-radius: 4px; 
                            cursor: pointer; font-weight: 700; letter-spacing: 0.5px;">VERIFY</button>
                `;
                header.appendChild(btnContainer);
            }
        }, 1000);
        poll();

        let chatHistory = [];
        let historyIndex = -1;

        function handleChatInputKeyDown(e) {
            if (e.key === 'Enter') {
                if (!e.shiftKey) {
                    e.preventDefault();
                    handleSendStop();
                }
                // If shiftKey is true, allow default newline
            }
        }
    
