
        window.VLI_DEBUG = true;
        let refreshCountdown = 60;
        
        const getSnaptradeSettings = () => ({
            SNAPTRADE_CLIENT_ID: localStorage.getItem('SNAPTRADE_CLIENT_ID') || '',
            SNAPTRADE_CONSUMER_KEY: localStorage.getItem('SNAPTRADE_CONSUMER_KEY') || '',
            SNAPTRADE_USER_ID: localStorage.getItem('SNAPTRADE_USER_ID') || '',
            SNAPTRADE_USER_SECRET: localStorage.getItem('SNAPTRADE_USER_SECRET') || ''
        });

        function openSnaptradeModal() {
            document.getElementById('snaptrade-modal').style.display = 'flex';
            document.getElementById('snaptrade-client-id').value = localStorage.getItem('SNAPTRADE_CLIENT_ID') || '';
            document.getElementById('snaptrade-client-secret').value = localStorage.getItem('SNAPTRADE_CONSUMER_KEY') || '';
            document.getElementById('snaptrade-user-id').value = localStorage.getItem('SNAPTRADE_USER_ID') || '';
            document.getElementById('snaptrade-user-secret').value = localStorage.getItem('SNAPTRADE_USER_SECRET') || '';
        }

        function closeSnaptradeModal() {
            document.getElementById('snaptrade-modal').style.display = 'none';
        }

        async function registerSnaptrade() {
            const clientId = document.getElementById('snaptrade-client-id').value.trim();
            const consumerKey = document.getElementById('snaptrade-client-secret').value.trim();
            const userId = document.getElementById('snaptrade-user-id').value.trim();
            
            if (clientId) localStorage.setItem('SNAPTRADE_CLIENT_ID', clientId);
            if (consumerKey) localStorage.setItem('SNAPTRADE_CONSUMER_KEY', consumerKey);
            
            try {
                const res = await fetch('/api/brokerage/register', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ client_id: clientId, consumer_key: consumerKey, user_id: userId })
                });
                const data = await res.json();
                if(data.user_secret) {
                    localStorage.setItem('SNAPTRADE_USER_ID', data.user_id);
                    localStorage.setItem('SNAPTRADE_USER_SECRET', data.user_secret);
                    document.getElementById('snaptrade-user-id').value = data.user_id;
                    document.getElementById('snaptrade-user-secret').value = data.user_secret;
                    alert('Registration Successful! You can now click Connect Broker Portal.');
                } else {
                    alert('Registration Failed: ' + JSON.stringify(data));
                }
            } catch(e) { alert(e); }
        }

        async function connectSnaptrade() {
            const clientId = document.getElementById('snaptrade-client-id').value.trim();
            const consumerKey = document.getElementById('snaptrade-client-secret').value.trim();
            const userId = document.getElementById('snaptrade-user-id').value.trim();
            const userSecret = document.getElementById('snaptrade-user-secret').value.trim();
            
            try {
                const res = await fetch('/api/brokerage/login', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify({ client_id: clientId, consumer_key: consumerKey, user_id: userId, user_secret: userSecret })
                });
                const data = await res.json();
                if(data.redirect_uri) {
                    window.open(data.redirect_uri, '_blank');
                    closeSnaptradeModal();
                } else {
                    alert('Connection Failed: ' + JSON.stringify(data));
                }
            } catch(e) { alert(e); }
        }

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
        const UX_CARD_LIMIT = 16;
        
        const CARD_TYPES = {
            'VLI_CHAT': { idPrefix: 'CI', title: 'Coordinator Interface', isSingleton: true },
            'VLI_TELEMETRY': { idPrefix: 'TM', title: 'System Telemetry', isSingleton: true },
            'MACRO_WL': { idPrefix: 'WL', title: 'Macro Watchlist', isSingleton: false },
            'STRUCTURAL_ANALY': { idPrefix: 'AR', title: 'Structural Analysis', isSingleton: false },
            'SCAN_RES': { idPrefix: 'SR', title: 'Market Scan', isSingleton: false },
            'ORDER_HIST': { idPrefix: 'OH', title: 'Portfolio', isSingleton: true },
            'SCHEDULER_LOG': { idPrefix: 'SL', title: 'Scheduler Telemetry', isSingleton: true }
        };

        class UXCardManager {
            constructor() {
                this.instances = {};
                this.typeCounts = { 'VLI_CHAT': 0, 'VLI_TELEMETRY': 0, 'MACRO_WL': 0, 'STRUCTURAL_ANALY': 0, 'SCAN_RES': 0, 'ORDER_HIST': 0, 'SCHEDULER_LOG': 0 };
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
                if (defaultStyles.right && defaultStyles.right !== 'auto') {
                    cardBox.style.left = 'auto';
                    cardBox.style.right = defaultStyles.right;
                }
                cardBox.style.width = defaultStyles.width || '440px';
                cardBox.style.height = defaultStyles.height || '360px';
                cardBox.style.zIndex = ++winManager.maxZ;

                cardBox.addEventListener('mousedown', (e) => {
                    bringToFront(cardBox);
                    if (e.target.closest('.card-header') && !e.target.classList.contains('win-btn')) {
                        winManager.dragging = cardBox;
                        winManager.draggingOriginalZ = cardBox.style.zIndex;
                        cardBox.style.zIndex = '999999';
                        cardBox.classList.add('is-dragging');
                        winManager.startX = e.clientX;
                        winManager.startY = e.clientY;
                        winManager.startTop = cardBox.offsetTop;
                        winManager.startLeft = cardBox.offsetLeft;
                        
                        document.addEventListener('mousemove', onMouseMove);
                        document.addEventListener('mouseup', onMouseUp);
                    }
                });

                const liveBadgeHTML = '';
                
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
                                        <th style="text-align: right; padding-right: 16px;">TREND (5M)</th>
                                    </tr>
                                </thead>
                                <tbody class="macro-watchlist-body-instance" id="macro-watchlist-body-${instanceGuid}" data-guid="${instanceGuid}">
                                    <tr><td colspan="5" style="text-align:center; padding:20px;">Standby...</td></tr>
                                </tbody>
                            </table>
                        </div>`;
                } else if (typeGuid === 'STRUCTURAL_ANALY') {
                    bodyContent = `
                        <div class="card-body terminal analysis-report-body analysis-report-viewer-instance" id="analysis-report-viewer-${instanceGuid}" data-guid="${instanceGuid}">
                            <div style="color:var(--text-muted); text-align:center; padding:40px;">No report active.</div>
                        </div>`;
                } else if (typeGuid === 'SCAN_RES') {
                    bodyContent = `
                        <div class="card-body" style="overflow-y: auto; padding: 10px;">
                        </div>`;
                } else if (typeGuid === 'ORDER_HIST') {
                    // Inject global tab switcher if not defined
                    if (!window.switchOrderTab) {
                        window.switchOrderTab = function(guid, tabId) {
                            document.getElementById(`positions-view-${guid}`).style.display = (tabId === 'positions') ? 'block' : 'none';
                            document.getElementById(`closed-positions-view-${guid}`).style.display = (tabId === 'closed') ? 'block' : 'none';
                            document.getElementById(`order-history-view-${guid}`).style.display = (tabId === 'history') ? 'block' : 'none';
                            
                            document.getElementById(`tab-btn-positions-${guid}`).style.background = (tabId === 'positions') ? 'var(--cobalt-blue)' : 'transparent';
                            document.getElementById(`tab-btn-positions-${guid}`).style.color = (tabId === 'positions') ? 'white' : 'var(--text-muted)';
                            
                            document.getElementById(`tab-btn-closed-${guid}`).style.background = (tabId === 'closed') ? 'var(--cobalt-blue)' : 'transparent';
                            document.getElementById(`tab-btn-closed-${guid}`).style.color = (tabId === 'closed') ? 'white' : 'var(--text-muted)';
                            
                            document.getElementById(`tab-btn-history-${guid}`).style.background = (tabId === 'history') ? 'var(--cobalt-blue)' : 'transparent';
                            document.getElementById(`tab-btn-history-${guid}`).style.color = (tabId === 'history') ? 'white' : 'var(--text-muted)';
                        };
                    }

                    bodyContent = `
                        <div class="card-body" style="overflow-y: hidden; padding: 10px; display: flex; flex-direction: column;">
                            <div style="display:flex; flex-direction:column; gap:8px; margin-bottom: 10px; padding: 10px; background: rgba(0,0,0,0.2); border-radius: 4px; border: 1px solid var(--border-color);">
                                <div style="display:flex; gap: 10px; align-items:center;">
                                    <select id="order-hist-account-${instanceGuid}" class="vli-input" style="flex:1;" onchange="fetchOrderHistory('${instanceGuid}')">
                                        <option value="">Loading Accounts...</option>
                                    </select>
                                </div>
                                <div style="display:flex; gap: 5px; align-items:center;">
                                    <select id="order-hist-range-${instanceGuid}" class="vli-input" style="flex:1;" onchange="setOrderHistoryRange(this.value, '${instanceGuid}')">
                                        <option value="today">Today</option>
                                        <option value="week">Past Week</option>
                                        <option value="month">Past Month</option>
                                        <option value="ytd">Year-to-Date</option>
                                        <option value="1y">Past Year</option>
                                        <option value="custom">Custom</option>
                                    </select>
                                </div>
                                <div style="display:flex; gap: 5px; align-items:center;">
                                    <input type="date" id="order-hist-start-${instanceGuid}" class="vli-input" style="flex:1;" autocomplete="off" data-dashlane_disable_autofill="true" data-lpignore="true" data-form-type="other" onchange="window.validateOrderDateRange('start', '${instanceGuid}'); document.getElementById('order-hist-range-${instanceGuid}').value='custom'; fetchOrderHistory('${instanceGuid}');">
                                    <input type="date" id="order-hist-end-${instanceGuid}" class="vli-input" style="flex:1;" autocomplete="off" data-dashlane_disable_autofill="true" data-lpignore="true" data-form-type="other" onchange="window.validateOrderDateRange('end', '${instanceGuid}'); document.getElementById('order-hist-range-${instanceGuid}').value='custom'; fetchOrderHistory('${instanceGuid}');">
                                    <input type="text" id="order-hist-symbol-${instanceGuid}" class="vli-input" placeholder="Sym" style="width: 50px; text-transform: uppercase;" autocomplete="off" data-dashlane_disable_autofill="true" data-lpignore="true" data-form-type="other" onchange="fetchOrderHistory('${instanceGuid}')" onkeydown="if(event.key === 'Enter') fetchOrderHistory('${instanceGuid}')">
                                    <button id="order-hist-filter-btn-${instanceGuid}" class="vli-btn" onclick="fetchOrderHistory('${instanceGuid}')" style="background:var(--cobalt-blue); border:none; color:#fff; padding:6px 12px; border-radius:4px; font-weight:700; cursor:pointer;">Filter</button>
                                </div>
                            </div>
                            
                            <div id="pnl-summary-${instanceGuid}" style="display:flex; justify-content: space-between; padding: 8px 12px; background: #1a1a1a; border-bottom: 1px solid var(--border-color); font-family: var(--font-mono); font-size: 11px;">
                                <div style="color: var(--text-muted);">Day PnL: <span id="pnl-day-${instanceGuid}">$0.00</span></div>
                                <div style="color: var(--text-muted);">Unrealized: <span id="pnl-unrealized-${instanceGuid}">$0.00</span></div>
                                <div style="color: var(--text-muted);">Realized (Range): <span id="pnl-realized-${instanceGuid}">$0.00</span></div>
                                <div style="color: var(--text-muted); font-weight: bold;">Total PnL: <span id="pnl-total-${instanceGuid}">$0.00</span></div>
                            </div>
                            
                            <div style="display:flex; border-bottom: 1px solid var(--border-color); margin-bottom: 10px;">
                                <button id="tab-btn-positions-${instanceGuid}" onclick="window.switchOrderTab('${instanceGuid}', 'positions')" style="background:var(--cobalt-blue); color:white; border:none; padding:8px 16px; cursor:pointer; font-weight:bold; font-size:11px;">Positions</button>
                                <button id="tab-btn-closed-${instanceGuid}" onclick="window.switchOrderTab('${instanceGuid}', 'closed')" style="background:transparent; color:var(--text-muted); border:none; padding:8px 16px; cursor:pointer; font-weight:bold; font-size:11px;">Closed Positions</button>
                                <button id="tab-btn-history-${instanceGuid}" onclick="window.switchOrderTab('${instanceGuid}', 'history')" style="background:transparent; color:var(--text-muted); border:none; padding:8px 16px; cursor:pointer; font-weight:bold; font-size:11px;">Order History</button>
                            </div>

                            <div id="positions-view-${instanceGuid}" style="flex-grow: 1; overflow-y: auto; border: 1px solid var(--border-color);">
                                <table class="macro-table ibkr-style-table" style="width:100%; border-collapse:collapse; font-size:11px;">
                                    <thead style="position:sticky; top:0; background:#1e1e1e; z-index:1;">
                                        <tr>
                                            <th style="padding:4px; text-align:left; border-bottom:1px solid #444;">TIME</th>
                                            <th style="padding:4px; text-align:left; border-bottom:1px solid #444;">SYM</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">LAST</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">DAY G/L%</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">DAY G/L$</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">TOT G/L%</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">TOT G/L$</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">QTY</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">AVG COST</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">VALUE</th>
                                        </tr>
                                    </thead>
                                    <tbody id="positions-body-${instanceGuid}" style="font-family: var(--font-mono);">
                                        <tr><td colspan="10" style="text-align:center; padding:20px; color:var(--text-muted);">Select filters...</td></tr>
                                    </tbody>
                                </table>
                            </div>

                            <div id="order-history-view-${instanceGuid}" style="flex-grow: 1; overflow-y: auto; border: 1px solid var(--border-color); display:none;">
                                <table class="macro-table ibkr-style-table" style="width:100%; border-collapse:collapse; font-size:11px;">
                                    <thead style="position:sticky; top:0; background:#1e1e1e; z-index:1;">
                                        <tr>
                                            <th style="padding:4px; text-align:left; border-bottom:1px solid #444;">TIME</th>
                                            <th style="padding:4px; text-align:left; border-bottom:1px solid #444;">SYM</th>
                                            <th style="padding:4px; text-align:left; border-bottom:1px solid #444;">ACTION</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">QTY</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">PRICE</th>
                                        </tr>
                                    </thead>
                                    <tbody id="order-history-body-${instanceGuid}" style="font-family: var(--font-mono);">
                                        <tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-muted);">Select filters...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                            
                            <div id="closed-positions-view-${instanceGuid}" style="flex-grow: 1; overflow-y: auto; border: 1px solid var(--border-color); display:none;">
                                <table class="macro-table ibkr-style-table" style="width:100%; border-collapse:collapse; font-size:11px;">
                                    <thead style="position:sticky; top:0; background:#1e1e1e; z-index:1;">
                                        <tr>
                                            <th style="padding:4px; text-align:left; border-bottom:1px solid #444;">TIME</th>
                                            <th style="padding:4px; text-align:left; border-bottom:1px solid #444;">SYM</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">QTY</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">BUY PRICE</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">SELL PRICE</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">PROFIT/LOSS ($)</th>
                                            <th style="padding:4px; text-align:right; border-bottom:1px solid #444;">PROFIT/LOSS (%)</th>
                                        </tr>
                                    </thead>
                                    <tbody id="closed-positions-body-${instanceGuid}" style="font-family: var(--font-mono);">
                                        <tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-muted);">Select filters...</td></tr>
                                    </tbody>
                                </table>
                            </div>
                        </div>`;
                } else if (typeGuid === 'SCHEDULER_LOG') {
                    bodyContent = `
                        <div class="card-body" style="padding:0; overflow:hidden; display:flex; flex-direction:column;">
                            <div class="chat-messages terminal" id="scheduler-log-messages-${instanceGuid}" style="padding-bottom: 20px; overflow-y: auto;">
                                <div style="color: var(--text-muted); padding: 10px;">Initializing Scheduler Telemetry...</div>
                            </div>
                        </div>`;
                } else if (typeDef.initContent) {
                    bodyContent = typeDef.initContent(instanceGuid);
                }

                cardBox.innerHTML = `
                    <div class="card-header">
                        <div style="display:flex; align-items:center; gap:8px;">
                            <div class="descriptor" style="cursor: pointer; transition: transform 0.1s;" onclick="insertCardIdIntoChat('${badgeLabel}')" onmouseover="this.style.transform='scale(1.1)'" onmouseout="this.style.transform='scale(1)'" title="Insert ${badgeLabel} to Chat">${badgeLabel}</div>
                            <div>${typeDef.title} ${liveBadgeHTML}</div>
                        </div>
                        <div class="card-controls">
                            <div class="win-btn win-dock" onclick="dockWindow('win-${instanceGuid}')" title="Dock to Main Workspace"></div>
                            <div class="win-btn win-min" onclick="toggleCollapse('win-${instanceGuid}')" title="Collapse"></div>
                            ${typeGuid === 'VLI_CHAT' ? '' : `<div class="win-btn win-pop" onclick="popoutWindow('win-${instanceGuid}')" title="Pop-out"></div>`}
                            <div class="win-btn win-max" onclick="maxWin('win-${instanceGuid}')" title="Maximize"></div>
                            <div class="win-btn win-close" onclick="UXManager.removeCard('${instanceGuid}')" title="Close"></div>
                        </div>
                    </div>
                    ${bodyContent}
                    <div class="resize-handle resize-n" data-dir="n"></div>
                    <div class="resize-handle resize-s" data-dir="s"></div>
                    <div class="resize-handle resize-e" data-dir="e"></div>
                    <div class="resize-handle resize-w" data-dir="w"></div>
                    <div class="resize-handle resize-nw" data-dir="nw"></div>
                    <div class="resize-handle resize-ne" data-dir="ne"></div>
                    <div class="resize-handle resize-sw" data-dir="sw"></div>
                    <div class="resize-handle resize-se" data-dir="se"></div>
                `;

                document.getElementById('wm-workspace').appendChild(cardBox);
                this.instances[instanceGuid] = cardBox;
                
                if (typeGuid === 'SCAN_RES' && typeof updateScannerResultsUI === 'function') {
                    setTimeout(() => {
                        updateScannerResultsUI();
                    }, 50);
                }
                
                if (typeGuid === 'VLI_CHAT') {
                    const inputElement = document.getElementById('chat-input');
                    if (inputElement) {
                        inputElement.addEventListener('keydown', handleChatInputKeyDown);
                    }
                } else if (typeGuid === 'ORDER_HIST') {
                    populateSnaptradeAccounts(instanceGuid);
                    setOrderHistoryRange('today', instanceGuid);
                    // Live auto-update every 10 seconds
                    setInterval(() => {
                        const box = document.getElementById('win-' + instanceGuid);
                        if(box && box.style.display !== 'none') {
                            // Only auto-fetch if we are looking at 'today'
                            const startVal = document.getElementById(`order-hist-start-${instanceGuid}`).value;
                            const d = new Date();
                            const todayStr = new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0];
                            if(startVal === todayStr) {
                                fetchOrderHistory(instanceGuid, true);
                            }
                        }
                    }, 10000);
                } else if (typeGuid === 'SCHEDULER_LOG') {
                    window.fetchSchedulerLogs(instanceGuid);
                    setInterval(() => {
                        const box = document.getElementById('win-' + instanceGuid);
                        if(box && box.style.display !== 'none') {
                            window.fetchSchedulerLogs(instanceGuid);
                        }
                    }, 5000);
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

                if (document.body.classList.contains('standalone')) {
                    header.draggable = true;
                    header.addEventListener('dragstart', (e) => {
                        e.dataTransfer.setData('text/plain', JSON.stringify({
                            action: 'REDOCK_WINDOW',
                            typeGuid: cardBox.dataset.typeGuid,
                            popoutId: cardBox.id
                        }));
                        e.dataTransfer.effectAllowed = 'move';
                    });
                }

                header.addEventListener('mousedown', (e) => {
                    bringToFront(cardBox);
                    if (e.target.classList.contains('win-btn')) return;
                    
                    if (document.body.classList.contains('standalone')) {
                        return; // Allow native HTML5 drag in standalone mode
                    }
                    
                    e.preventDefault();
                    
                    winManager.dragging = cardBox;
                    winManager.draggingOriginalZ = cardBox.style.zIndex;
                    cardBox.style.zIndex = '999999';
                    cardBox.classList.add('is-dragging');
                    winManager.startX = e.clientX;
                    winManager.startY = e.clientY;
                    winManager.startTop = cardBox.offsetTop;
                    winManager.startLeft = cardBox.offsetLeft;
                    
                    document.addEventListener('mousemove', onMouseMove);
                    document.addEventListener('mouseup', onMouseUp);
                });

                cardBox.querySelectorAll('.resize-handle').forEach(resizer => {
                    resizer.addEventListener('mousedown', (e) => {
                        bringToFront(cardBox);
                        winManager.resizing = cardBox;
                        winManager.resizeDir = resizer.dataset.dir;
                        winManager.startX = e.clientX;
                        winManager.startY = e.clientY;
                        winManager.startW = cardBox.offsetWidth;
                        winManager.startH = cardBox.offsetHeight;
                        winManager.startTop = cardBox.offsetTop;
                        winManager.startLeft = cardBox.offsetLeft;
                        
                        document.addEventListener('mousemove', onMouseMove);
                        document.addEventListener('mouseup', onMouseUp);
                        e.preventDefault();
                    });
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
            // Removed generic listener attachment, now handled dynamically per card in createCard
        }

            // Removed generic resize bindings since UXCardManager injects them dynamically

        let snapModeEnabled = true;

        function toggleSnapMode() {
            snapModeEnabled = !snapModeEnabled;
            const statusEl = document.getElementById('menu-snap-status');
            if (statusEl) statusEl.innerText = snapModeEnabled ? "ON" : "OFF";
        }

        function onMouseMove(e) {
            const now = performance.now();
            if (winManager.lastTime) {
                const dt = now - winManager.lastTime;
                if (dt > 0) {
                    const dxVel = e.clientX - winManager.lastX;
                    const dyVel = e.clientY - winManager.lastY;
                    const vel = Math.sqrt(dxVel*dxVel + dyVel*dyVel) / dt;
                    winManager.velocity = (winManager.velocity || 0) * 0.8 + vel * 0.2;
                }
            } else {
                winManager.velocity = 0;
            }
            winManager.lastX = e.clientX;
            winManager.lastY = e.clientY;
            winManager.lastTime = now;
            
            let velMultiplier = 1.0;
            if (winManager.velocity > 0.05) {
                velMultiplier = Math.max(0, 1.0 - ((winManager.velocity - 0.05) * 4.0));
            }

            if (winManager.dragging) {
                const dx = e.clientX - winManager.startX;
                const dy = e.clientY - winManager.startY;
                
                let rawTop = winManager.startTop + dy;
                let rawLeft = winManager.startLeft + dx;
                let newTop = rawTop;
                let newLeft = rawLeft;
                
                // --- PULL-AWAY COOLDOWN (Graceful Hysteresis) ---
                let timeSinceBreak = Date.now() - (winManager.snapBreakTime || 0);
                let snapStrength = 1.0;
                if (timeSinceBreak < 2000) snapStrength = 0;
                else if (timeSinceBreak < 5000) snapStrength = (timeSinceBreak - 2000) / 3000;
                
                // --- KINEMATIC INFLUENCE ---
                snapStrength *= velMultiplier;
                
                if (winManager.isSnapped && snapModeEnabled && snapStrength > 0.5) {
                    const pullDist = Math.max(Math.abs(rawTop - winManager.snappedTop), Math.abs(rawLeft - winManager.snappedLeft));
                    if (pullDist > 40) {
                        winManager.snapBreakTime = Date.now();
                        winManager.isSnapped = false;
                        snapStrength = 0;
                    }
                }
                
                let isOffCanvas = winManager.dragging.dataset.artifactPath && e.clientX < 300;
                
                if (isOffCanvas) {
                    document.querySelectorAll('.tree-folder > .tree-item').forEach(node => {
                        node.style.backgroundColor = '';
                    });
                    
                    const elemUnder = document.elementFromPoint(e.clientX, e.clientY);
                    if (elemUnder) {
                        const treeNode = elemUnder.closest('.tree-folder');
                        if (treeNode) {
                            const treeItem = treeNode.querySelector(':scope > .tree-item');
                            if (treeItem) treeItem.style.backgroundColor = 'rgba(88, 166, 255, 0.2)';
                        }
                    }
                }

                let didSnap = false;
                if (!isOffCanvas && snapModeEnabled && snapStrength > 0) {
                    const snapThreshold = 45 * snapStrength; // Dominant magnetic pull to other windows
                    const gridSnapThreshold = 8 * snapStrength; // Base background grid snap (micro-grid)
                    const elWidth = winManager.dragging.offsetWidth;
                    const elHeight = winManager.dragging.offsetHeight;
                    
                    // 1. Strict Top-Left Grid Anchorage (10px micro-grid instead of 40px)
                    const gridX = Math.round(newLeft / 10) * 10;
                    const gridY = Math.round(newTop / 10) * 10;
                    
                    if (Math.abs(newLeft - gridX) < gridSnapThreshold) { newLeft = gridX; didSnap = true; }
                    if (Math.abs(newTop - gridY) < gridSnapThreshold) { newTop = gridY; didSnap = true; }
                    
                    // 2. Strong Window-to-Window Snapping
                    document.querySelectorAll('.card').forEach(other => {
                        if (other === winManager.dragging || other.style.display === 'none') return;
                        const rect = other.getBoundingClientRect();
                        
                        // Vertical
                        if (Math.abs(newTop - rect.bottom) < snapThreshold) { newTop = rect.bottom; didSnap = true; }
                        if (Math.abs(newTop + elHeight - rect.top) < snapThreshold) { newTop = rect.top - elHeight; didSnap = true; }
                        if (Math.abs(newTop - rect.top) < snapThreshold) { newTop = rect.top; didSnap = true; }
                        // Horizontal
                        if (Math.abs(newLeft - rect.right) < snapThreshold) { newLeft = rect.right; didSnap = true; }
                        if (Math.abs(newLeft + elWidth - rect.left) < snapThreshold) { newLeft = rect.left - elWidth; didSnap = true; }
                        if (Math.abs(newLeft - rect.left) < snapThreshold) { newLeft = rect.left; didSnap = true; }
                    });
                }
                
                if (didSnap) {
                    winManager.isSnapped = true;
                    winManager.snappedTop = newTop;
                    winManager.snappedLeft = newLeft;
                } else {
                    winManager.isSnapped = false;
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
                const dir = winManager.resizeDir;
                const card = winManager.resizing;

                const gridSnapThreshold = 14 * velMultiplier; 
                let newLeft = winManager.startLeft;
                let newTop = winManager.startTop;
                let newW = winManager.startW;
                let newH = winManager.startH;

                if (dir.includes('e')) {
                    newW = Math.max(200, winManager.startW + dx);
                    if (snapModeEnabled) {
                        let newRight = winManager.startLeft + newW;
                        let gridRight = Math.round(newRight / 40) * 40;
                        if (Math.abs(newRight - gridRight) < gridSnapThreshold) newW = gridRight - winManager.startLeft;
                    }
                }
                if (dir.includes('s')) {
                    newH = Math.max(100, winManager.startH + dy);
                    if (snapModeEnabled) {
                        let newBottom = winManager.startTop + newH;
                        let gridBottom = Math.round(newBottom / 40) * 40;
                        if (Math.abs(newBottom - gridBottom) < gridSnapThreshold) newH = gridBottom - winManager.startTop;
                    }
                }
                if (dir.includes('w')) {
                    newLeft = winManager.startLeft + dx;
                    if (snapModeEnabled) {
                        let gridLeft = Math.round(newLeft / 40) * 40;
                        if (Math.abs(newLeft - gridLeft) < gridSnapThreshold) newLeft = gridLeft;
                    }
                    newW = winManager.startW + (winManager.startLeft - newLeft);
                    if (newW < 200) { newW = 200; newLeft = winManager.startLeft + winManager.startW - 200; }
                }
                if (dir.includes('n')) {
                    newTop = winManager.startTop + dy;
                    if (snapModeEnabled) {
                        let gridTop = Math.round(newTop / 40) * 40;
                        if (Math.abs(newTop - gridTop) < gridSnapThreshold) newTop = gridTop;
                    }
                    newH = winManager.startH + (winManager.startTop - newTop);
                    if (newH < 100) { newH = 100; newTop = winManager.startTop + winManager.startH - 100; }
                }

                if (dir.includes('w') || dir.includes('e')) {
                    card.style.width = newW + 'px';
                    if (dir.includes('w')) card.style.left = newLeft + 'px';
                }
                if (dir.includes('n') || dir.includes('s')) {
                    card.style.height = newH + 'px';
                    if (dir.includes('n')) card.style.top = newTop + 'px';
                }
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
                    // Optimized High-Fidelity Workspace Layout
                    // UXManager.createCard('VLI_CHAT', {top: '2%', left: '66%', width: '33%', height: '96%'}, 'coordinator');
                    UXManager.createCard('MACRO_WL', {top: '2%', left: '1%', width: '19%', height: '55%'}, 'watchlist');
                    UXManager.createCard('SCAN_RES', {top: '2%', left: '21%', width: '21%', height: '55%'}, 'scanner');
                    UXManager.createCard('SCAN_RES', {top: '2%', left: '43%', width: '22%', height: '55%'}, 'shield');
                    
                    // Add RUN button to Scanner Results header for backup
                    setTimeout(() => {
                        const scHeader = document.querySelector('.card[data-type-guid="SCAN_RES"] .card-header');
                        if (scHeader && !document.getElementById('sr-run-btn')) {
                            const btnContainer = document.createElement('div');
                            btnContainer.style.display = 'flex';
                            btnContainer.style.alignItems = 'center';
                            btnContainer.style.gap = '6px';
                            btnContainer.innerHTML = `
                                <button id="sr-run-btn" onclick="initScannerSSE()" 
                                        style="background: rgba(63, 185, 80, 0.1); border: 1px solid rgba(63, 185, 80, 0.4); 
                                        color: var(--emerald-green); font-size: 9px; padding: 2px 6px; border-radius: 4px; 
                                        cursor: pointer; font-weight: 700;">RUN</button>
                                <button id="sr-stop-btn" onclick="stopScanner()" 
                                        style="background: rgba(248, 81, 73, 0.1); border: 1px solid rgba(248, 81, 73, 0.4); 
                                        color: var(--ruby-red); font-size: 9px; padding: 2px 6px; border-radius: 4px; 
                                        cursor: pointer; font-weight: 700;">STOP</button>
                            `;
                            scHeader.insertBefore(btnContainer, scHeader.querySelector('.card-controls'));
                        }
                    }, 500);
                    UXManager.createCard('ORDER_HIST', {top: '59%', left: '1%', width: '41%', height: '39%'}, 'order_history');
                    UXManager.createCard('VLI_TELEMETRY', {top: '59%', left: '43%', width: '22%', height: '39%'}, 'telemetry');
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
                    
                    if (state.typeGuid === 'SHIELD_RES') {
                        state.typeGuid = 'SCAN_RES';
                        state.instanceGuid = 'shield';
                    }
                    if (state.typeGuid === 'SCAN_RES' && state.instanceGuid !== 'scanner' && state.instanceGuid !== 'shield') {
                        continue; // Self-heal: Drop anomalous/legacy scan windows that lack proper initialization GUIDs
                    }
                    
                    let card;
                    if (state.typeGuid === 'VLI_CHAT' && UXManager.instances[state.instanceGuid]) {
                        card = UXManager.instances[state.instanceGuid];
                        if (state.top) card.style.top = state.top;
                        if (state.left) card.style.left = state.left;
                        if (state.right && state.right !== 'auto') { card.style.right = state.right; card.style.left = 'auto'; }
                        if (state.width) card.style.width = state.width;
                        if (state.height) card.style.height = state.height;
                    } else if (state.typeGuid !== 'VLI_CHAT') {
                        card = UXManager.createCard(state.typeGuid, state, state.instanceGuid);
                    }
                    if (card) {
                        if (state.display) card.style.display = state.display;
                        if (state.collapsed) card.classList.add('collapsed');
                        const z = parseInt(state.zIndex) || 100;
                        if (z > winManager.maxZ) winManager.maxZ = z;
                        
                        // [UI HARDENING] Enforce viewport bounds constraint for legacy saved layouts
                        setTimeout(() => {
                            const rect = card.getBoundingClientRect();
                            if (state.typeGuid === 'VLI_CHAT') {
                                // Clamp coordinator strictly to 1/3 viewport if missing bounds
                                if (rect.right > (window.innerWidth + 5) || rect.bottom > (window.innerHeight + 5) || rect.width > window.innerWidth * 0.4) {
                                    card.style.top = '2%';
                                    card.style.left = '66%';
                                    card.style.width = '33%';
                                    card.style.height = '96%';
                                }
                            } else {
                                // Auto-correct standard panels safely
                                if (rect.right > window.innerWidth) card.style.width = Math.max(300, window.innerWidth - rect.left - 15) + 'px';
                                if (rect.bottom > window.innerHeight) card.style.height = Math.max(200, window.innerHeight - rect.top - 15) + 'px';
                            }
                        }, 50);
                    }
                }
                
                // Self-healing: Ensure both institutional scanners are always present
                if (!Object.values(UXManager.instances).find(c => c.dataset.instanceGuid === 'scanner')) {
                    UXManager.createCard('SCAN_RES', {top: '2%', left: '21%', width: '21%', height: '55%'}, 'scanner');
                }
                if (!Object.values(UXManager.instances).find(c => c.dataset.instanceGuid === 'shield')) {
                    UXManager.createCard('SCAN_RES', {top: '2%', left: '43%', width: '22%', height: '55%'}, 'shield');
                }
            } catch(e) {}
        }

        function loadLayout() {
            const urlParams = new URLSearchParams(window.location.search);
            if (urlParams.get('popout')) return;
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
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="switchSidebarTab('coordinator')" style="color:var(--emerald-green);">[+] Open Coordinator</div>`;
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'VLI_TELEMETRY')) {
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="UXManager.createCard('VLI_TELEMETRY')" style="color:var(--emerald-green);">[+] Spawn System Telemetry</div>`;
            }
            
            if (!Object.values(UXManager.instances).find(c => c.dataset.instanceGuid === 'scanner')) {
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="UXManager.createCard('SCAN_RES', {}, 'scanner')" style="color:var(--emerald-green);">[+] Spawn Sortino Sniper</div>`;
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.instanceGuid === 'shield')) {
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="UXManager.createCard('SCAN_RES', {}, 'shield')" style="color:var(--emerald-green);">[+] Spawn Apex Core Scan</div>`;
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'SCHEDULER_LOG')) {
                 viewMenu.innerHTML += `<div class="dropdown-item" onclick="UXManager.createCard('SCHEDULER_LOG')" style="color:var(--emerald-green);">[+] Spawn Scheduler Log</div>`;
            }

            if (keys.length > 0) viewMenu.innerHTML += '<div class="dropdown-divider"></div>';

            keys.forEach(guid => {
                const card = UXManager.instances[guid];
                const badge = card.dataset.badge;
                
                let title = CARD_TYPES[card.dataset.typeGuid].title;
                
                // If it's an Analysis Report (UX Report), attempt to grab the descriptive dynamic title
                if (card.dataset.typeGuid === 'STRUCTURAL_ANALY') {
                    const titleElem = card.querySelector('.card-header > div:first-child > div:nth-child(2)');
                    if (titleElem) {
                        // Extract text and remove the LIVE badge if present
                        let text = titleElem.innerText || '';
                        text = text.replace('LIVE', '').trim();
                        if (text && text.length > 0) {
                            title = text;
                        }
                    }
                }
                
                const isVisible = card.style.display !== 'none';
                
                const check = isVisible ? '' : '☐';
                const el = document.createElement('div');
                el.className = 'dropdown-item';
                el.innerHTML = `<span>[${badge}] ${title}</span> <span style="font-size: 11px; margin-left: 20px;">${check}</span>`;
                el.onclick = () => {
                    if (isVisible) {
                        card.style.display = 'none';
                    } else {
                        card.style.display = '';
                        bringToFront(card);
                    }
                    saveLayout();
    
            if (!Object.values(UXManager.instances).find(c => c.dataset.instanceGuid === 'scanner')) {
                 UXManager.createCard('SCAN_RES', {top: '2%', left: '33.5%', width: '31%', height: '47%'}, 'scanner');
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.instanceGuid === 'shield')) {
                 UXManager.createCard('SCAN_RES', {top: '51%', left: '33.5%', width: '31%', height: '47%'}, 'shield');
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'SCHEDULER_LOG')) {
                 UXManager.createCard('SCHEDULER_LOG', {top: '51%', left: '66%', width: '33%', height: '47%'}, 'scheduler');
            }


            if (!Object.values(UXManager.instances).find(c => c.dataset.instanceGuid === 'scanner')) {
                 UXManager.createCard('SCAN_RES', {top: '2%', left: '33.5%', width: '31%', height: '47%'}, 'scanner');
            }
            if (!Object.values(UXManager.instances).find(c => c.dataset.instanceGuid === 'shield')) {
                 UXManager.createCard('SCAN_RES', {top: '51%', left: '33.5%', width: '31%', height: '47%'}, 'shield');
            }

                updateViewMenu();
                };
                viewMenu.appendChild(el);
            });
        }

        function onMouseUp(e) {
            document.querySelectorAll('.tree-folder > .tree-item').forEach(node => {
                node.style.backgroundColor = '';
            });
            
            if (winManager.dragging) {
                if (e && winManager.dragging.dataset.artifactPath) {
                    const elemUnder = document.elementFromPoint(e.clientX, e.clientY);
                    if (elemUnder) {
                        const treeNode = elemUnder.closest('.tree-folder');
                        if (treeNode) {
                                const dragged = winManager.dragging;
                                const rect = dragged.getBoundingClientRect();
                                const targetRect = treeNode.getBoundingClientRect();
                                
                                const ghost = document.createElement('div');
                                ghost.style.position = 'fixed';
                                ghost.style.left = rect.left + 'px';
                                ghost.style.top = rect.top + 'px';
                                ghost.style.width = rect.width + 'px';
                                ghost.style.height = rect.height + 'px';
                                ghost.style.border = '2px dashed var(--cobalt-blue)';
                                ghost.style.borderRadius = '12px';
                                ghost.style.zIndex = '999999';
                                ghost.style.pointerEvents = 'none';
                                ghost.style.transition = 'all 0.4s cubic-bezier(0.25, 0.1, 0.25, 1)';
                                document.body.appendChild(ghost);
                                
                                const cardId = dragged.id.replace('win-', '');
                                UXManager.removeCard(cardId);
                                
                                requestAnimationFrame(() => {
                                    ghost.style.left = (targetRect.left + targetRect.width / 2) + 'px';
                                    ghost.style.top = (targetRect.top + targetRect.height / 2) + 'px';
                                    ghost.style.width = '10px';
                                    ghost.style.height = '10px';
                                    ghost.style.opacity = '0';
                                    ghost.style.transform = 'translate(-50%, -50%)';
                                });
                                
                                setTimeout(() => {
                                    if (ghost.parentNode) ghost.parentNode.removeChild(ghost);
                                    const treeItem = treeNode.querySelector(':scope > .tree-item');
                                    if (treeItem) {
                                        treeItem.style.transition = 'background-color 0.2s';
                                        treeItem.style.backgroundColor = 'rgba(88, 166, 255, 0.4)';
                                        setTimeout(() => { treeItem.style.backgroundColor = ''; }, 500);
                                    }
                                }, 400);

                                const targetFolderName = treeNode.dataset.path || treeNode.querySelector('.tree-label').innerText.trim();

                                fetch('/api/vli/artifacts/copy_to_folder', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({ source_path: dragged.dataset.artifactPath, target_folder: targetFolderName })
                                }).then(res => res.json())
                                  .then(data => {
                                      if (data.status === 'OK') {
                                          let folderBaseName = targetFolderName;
                                          if (folderBaseName.includes('/')) folderBaseName = folderBaseName.split('/').pop();
                                          if (folderBaseName.includes('\\')) folderBaseName = folderBaseName.split('\\').pop();
                                          window.vliForceOpenFolder = folderBaseName;
                                          loadArtifactTree();
                                      } else {
                                          console.error('Copy failed:', data.detail || data);
                                      }
                                  });
                                  
                                winManager.dragging = null;
                            }
                        }
                    }
                winManager.dragging.style.zIndex = winManager.draggingOriginalZ || winManager.maxZ;
                winManager.dragging.classList.remove('is-dragging');
                saveLayout();
            } else if (winManager.resizing) {
                saveLayout();
            }
            winManager.dragging = null;
            winManager.resizing = null;
            winManager.lastTime = null;
            document.removeEventListener('mousemove', onMouseMove);
            document.removeEventListener('mouseup', onMouseUp);
        }

        function dockWindow(id) {
            if (document.body.classList.contains('standalone')) {
                const cardEl = document.getElementById(id);
                if (cardEl) {
                    bc.postMessage({
                        type: 'REDOCK_WINDOW_API',
                        typeGuid: cardEl.dataset.typeGuid,
                        popoutId: cardEl.id
                    });
                }
            }
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
            // --- VLI ORCHESTRA STANDALONE DETECTION ---
            if (popoutId) {
                console.log("[VLI_ORCHESTRA] Satellite Mode Active for:", popoutId);
                document.body.classList.add('standalone');
                
                const popoutType = urlParams.get('type');
                if (popoutType) {
                    const instanceGuid = popoutId.replace('win-', '');
                    UXManager.createCard(popoutType, {}, instanceGuid);
                }
                
                const target = document.getElementById(popoutId);
                if (target) {
                    target.classList.add('popout-target');
                    target.style.position = 'static';
                    target.style.width = '100vw';
                    target.style.height = '100vh';
                }
                bc.onmessage = (e) => {
                    if (e.data.type === 'REDOCK_COMPLETE' && e.data.popoutId === popoutId) {
                        window.close();
                    }
                    if (e.data.type === 'STATE_UPDATE') {
                        const data = e.data.state;
                        renderTelemetry(data);
                        renderWatchlist(data);
                        renderReport(data);
                        renderMacros(data);
                        renderScannerResults(data);
                        renderShieldResults(data);
                        if (window.VLI_DEBUG) console.log("[VLI_ORCHESTRA] Satellite Node Re-Sync Successful.");
                    }
                };
            } else {
                bc.onmessage = (e) => {
                    if (e.data.type === 'REDOCK_WINDOW_API') {
                        const instanceGuid = e.data.popoutId.replace('win-', '');
                        UXManager.createCard(e.data.typeGuid, {}, instanceGuid);
                        bc.postMessage({ type: 'REDOCK_COMPLETE', popoutId: e.data.popoutId });
                    }
                };

                document.body.addEventListener('dragover', (e) => {
                    e.preventDefault();
                    e.dataTransfer.dropEffect = 'move';
                    document.body.classList.add('drag-hover');
                });
                document.body.addEventListener('dragleave', (e) => {
                    document.body.classList.remove('drag-hover');
                });
                document.body.addEventListener('drop', (e) => {
                    e.preventDefault();
                    document.body.classList.remove('drag-hover');
                    try {
                        const dataStr = e.dataTransfer.getData('text/plain');
                        if (dataStr) {
                            const data = JSON.parse(dataStr);
                            if (data.action === 'REDOCK_WINDOW') {
                                const instanceGuid = data.popoutId.replace('win-', '');
                                UXManager.createCard(data.typeGuid, {}, instanceGuid);
                                bc.postMessage({ type: 'REDOCK_COMPLETE', popoutId: data.popoutId });
                            }
                        }
                    } catch(err) { }
                });
            }
        });

        // --- VLI ORCHESTRA SPINE ---
        const bc = new BroadcastChannel('vli_spine');
        const urlParams = new URLSearchParams(window.location.search);
        const popoutId = urlParams.get('popout');

        function popoutWindow(id) {
            const cardEl = document.getElementById(id);
            const typeGuid = cardEl ? cardEl.dataset.typeGuid : '';
            const width = 800;
            const height = 600;
            const left = (screen.width - width) / 2;
            const top = (screen.height - height) / 2;
            window.open(window.location.href.split('?')[0] + '?popout=' + id + '&type=' + typeGuid, id, 
                `width=${width},height=${height},top=${top},left=${left},toolbar=no,menubar=no,status=no`);
            
            // Remove the card from the main UI
            if (id.startsWith('win-')) {
                UXManager.removeCard(id.replace('win-', ''));
            }
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
                    vliChatSyncPointer = 0; // Reset history pointer
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
            localStorage.removeItem('vli_wm_layout');
            location.reload();
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

        function arrangeWorkspace() {
            const vww = window.innerWidth;
            const vwh = window.innerHeight;
            
            // Grid math for exact 40px matrix alignment
            const rawChatWidth = vww / 3;
            const chatWidth = Math.round(rawChatWidth / 40) * 40;
            const chatLeft = Math.round((vww - chatWidth) / 40) * 40;
            const chatHeight = Math.round((vwh - 120) / 40) * 40;
            
            const leftWidth = chatLeft - 80; // 40px margin on both sides
            const leftWidthGrid = Math.round(leftWidth / 40) * 40;
            
            const chat = Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'VLI_CHAT');
            if (chat) {
                chat.style.display = '';
                chat.style.top = '40px';
                chat.style.left = chatLeft + 'px';
                chat.style.width = chatWidth + 'px';
                chat.style.height = chatHeight + 'px';
                bringToFront(chat);
            }
            
            const watchlist = Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'MACRO_WL');
            if (watchlist) {
                watchlist.style.display = '';
                watchlist.style.top = '40px';
                watchlist.style.left = '40px';
                watchlist.style.width = leftWidthGrid + 'px';
                watchlist.style.height = '400px';
                bringToFront(watchlist);
            }
            
            const telemetry = Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'VLI_TELEMETRY');
            if (telemetry) {
                telemetry.style.display = '';
                telemetry.style.top = '480px';
                telemetry.style.left = '40px';
                telemetry.style.width = leftWidthGrid + 'px';
                telemetry.style.height = '400px';
                bringToFront(telemetry);
            }
            
            const history = Object.values(UXManager.instances).find(c => c.dataset.typeGuid === 'ORDER_HIST');
            if (history) {
                history.style.display = '';
                history.style.top = '40px';
                history.style.left = '40px';
                history.style.width = leftWidthGrid + 'px';
                history.style.height = chatHeight + 'px';
                // push history to back behind telemetry/watchlist if all are open
                history.style.zIndex = Math.max(10, winManager.maxZ - 10); 
            }
            
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

        // --- MARKED CUSTOM RENDERER ---
        const renderer = new marked.Renderer();
        renderer.code = function(code, language) {
            const id = 'code-' + Math.random().toString(36).substr(2, 9);
            return `
                <div class="code-block-container" style="position: relative; margin: 10px 0;">
                    <button class="copy-code-btn" onclick="copyCode(this)" data-code-id="${id}" style="position: absolute; top: 10px; right: 10px; background: rgba(255,255,255,0.08); border: 1px solid rgba(255,255,255,0.1); color: var(--text-muted); padding: 4px 8px; border-radius: 4px; font-size: 10px; cursor: pointer; z-index: 10; font-family: var(--font-main); transition: all 0.2s;">Copy</button>
                    <pre style="margin:0;"><code id="${id}" class="language-${language}">${code}</code></pre>
                </div>
            `;
        };
        marked.setOptions({ renderer: renderer });

        async function copyCode(btn) {
            const id = btn.dataset.codeId;
            const code = document.getElementById(id).innerText;
            await navigator.clipboard.writeText(code);
            btn.innerText = 'Copied!';
            btn.style.color = 'var(--emerald-green)';
            setTimeout(() => { btn.innerText = 'Copy'; btn.style.color = ''; }, 2000);
        }

        async function copyMessage(btn) {
            const msgContent = btn.closest('.msg-ai-content').querySelector('.chat-inline-markdown').innerText;
            await navigator.clipboard.writeText(msgContent);
            const oldHtml = btn.innerHTML;
            btn.innerHTML = '';
            setTimeout(() => btn.innerHTML = oldHtml, 2000);
        }

        async function popoutMessage(btn) {
            const aiMsg = btn.closest('.msg-ai-content');
            let contentHtml = "";
            const inlineMd = aiMsg.querySelector('.chat-inline-markdown');
            if (inlineMd) {
                contentHtml = inlineMd.innerHTML;
            } else {
                contentHtml = aiMsg.innerHTML;
            }
            
            if (typeof CARD_TYPES !== 'undefined' && !CARD_TYPES['ARTIFACT_VIEWER']) {
                CARD_TYPES['ARTIFACT_VIEWER'] = {
                    idPrefix: "ART",
                    title: "Artifact Viewer",
                    isSingleton: false,
                    initContent: () => `<div class="artifact-content msg-ai" style="padding:15px; overflow-y:auto; height:100%;"></div>`,
                    onAttach: () => {}
                };
            }
            
            if (typeof UXManager !== 'undefined') {
                const card = UXManager.createCard('ARTIFACT_VIEWER', {
                    top: '100px', left: '100px', width: '700px', height: '600px'
                });
                
                if (card) {
                    const titleEl = card.querySelector('.card-header > div:first-child > div:nth-child(2)');
                    if (titleEl) titleEl.innerText = "Message Popout";
                    const contentEl = card.querySelector('.artifact-content');
                    if (contentEl) {
                        contentEl.innerHTML = contentHtml;
                        contentEl.style.color = "var(--text-muted)";
                    }
                }
            } else {
                console.warn("UXManager not found, falling back to window.alert");
                alert("Popout not available without UXManager.");
            }
        }

        // --- GEMINI MESSAGE RENDERING ENGINE ---
        function vliAppendMessage(container, msg) {
            try {
                if (msg.content && String(msg.content).includes('[SILENT_LOG]')) {
                    return;
                }
                if (window.VLI_DEBUG) console.log("[VLI_RENDER] Appending message:", msg);
                const isAI = msg.role === 'ai';
            const msgDiv = document.createElement('div');
            msgDiv.className = isAI ? 'msg msg-ai' : 'msg msg-user';
            
            if (isAI) {
                let thoughtHTML = "";
                if (msg.thought) {
                    const tid = 'thought-' + Math.random().toString(36).substr(2, 9);
                    thoughtHTML = `
                        <div class="thought-container">
                            <div class="thought-header" onclick="this.classList.toggle('open')">
                                <div class="thought-icon-chevron"><svg viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M6 9l6 6 6-6"/></svg></div>
                                <div class="gemini-sparkle"><svg viewBox="0 0 24 24" fill="currentColor"><path d="M12 2L14.5 9L22 11.5L14.5 14L12 21L9.5 14L2 11.5L9.5 9L12 2Z"/></svg></div>
                                <span>Show thinking</span>
                            </div>
                            <div class="thought-content">${marked.parse(msg.thought)}</div>
                        </div>
                    `;
                }
                
                msgDiv.innerHTML = `
                    <div class="msg-ai-content">
                        ${thoughtHTML}
                        <div class="chat-inline-markdown">${applyStatusFormatting(marked.parse(msg.content || ''))}</div>
                        <div style="font-size:10px; color:var(--text-muted); margin-top:12px; display:flex; gap:12px; align-items:center;">
                            <span>${msg.timestamp}</span>
                            <span style="cursor:pointer; opacity: 0.6; transition: opacity 0.2s;" onclick="popoutMessage(this)" title="Popout Message">
                                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                    <path d="M18 13v6a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V8a2 2 0 0 1 2-2h6"></path>
                                    <polyline points="15 3 21 3 21 9"></polyline>
                                    <line x1="10" y1="14" x2="21" y2="3"></line>
                                </svg>
                            </span>
                            <span style="cursor:pointer; opacity: 0.6; transition: opacity 0.2s;" onclick="copyMessage(this)" title="Copy Response">
                                <svg viewBox="0 0 24 24" width="14" height="14" stroke="currentColor" stroke-width="2" fill="none" stroke-linecap="round" stroke-linejoin="round">
                                    <rect x="9" y="9" width="13" height="13" rx="2" ry="2"></rect>
                                    <path d="M5 15H4a2 2 0 0 1-2-2V4a2 2 0 0 1 2-2h9a2 2 0 0 1 2 2v1"></path>
                                </svg>
                            </span>
                        </div>
                    </div>
                `;
            } else {
                msgDiv.innerText = msg.content;
            }
            
            container.appendChild(msgDiv);
            container.scrollTop = container.scrollHeight;
            
                // Render Math
                try {
                    renderMathInElement(msgDiv, {
                        delimiters: [
                            { left: '$$', right: '$$', display: true }
                        ]
                    });
                } catch (e) {
                    if (window.VLI_DEBUG) console.error("[VLI_RENDER] KaTeX error:", e);
                }
            } catch (err) {
                console.error("[VLI_RENDER] CRITICAL FAILURE:", err, msg);
            }
        }

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
        let vliChatSyncPointer = 0; // Tracks rendered messages in chat history

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
                const newCard = UXManager.createCard('STRUCTURAL_ANALY');
                reportViewer = newCard.querySelector('.analysis-report-viewer-instance');
            }

            let formattedText = text;
            const t = text.trim();
            
            // Dynamic Title Bar Extraction setup
            let dynamicTitle = "Structural Analysis";
            let lines = t.split('\n');
            let headerLine = lines.find(line => /^#{1,4}\s+/.test(line.trim()));
            if (headerLine) {
                dynamicTitle = headerLine.replace(/^#{1,4}\s+/, '').replace(/[\*\_`]/g, '').trim();
                if (dynamicTitle.length > 55) dynamicTitle = dynamicTitle.substring(0, 52) + "...";
            }
            
            if (t.startsWith('{') || t.startsWith('[')) {
                try {
                    const parsed = JSON.parse(t);
                    formattedText = "```json\n" + JSON.stringify(parsed, null, 2) + "\n```";
                } catch (e) {
                    formattedText = "```json\n" + text + "\n```";
                }
            }

            reportViewer.innerHTML = `<div class="msg-ai" style="padding: 15px;">${applyStatusFormatting(marked.parse(formattedText))}</div>`;
            reportViewer.scrollTop = 0;
            
            const card = reportViewer.closest('.card');
            
            // Inject dynamic title into the header while preserving the LIVE badge if present
            const titleElem = card.querySelector('.card-header > div:first-child > div:nth-child(2)');
            if (titleElem) {
                const badge = titleElem.querySelector('.live-badge');
                titleElem.innerHTML = dynamicTitle + (badge ? ' ' + badge.outerHTML : '');
            }
            
            // Bring the owning window to front
            bringToFront(card);
            
            try {
                renderMathInElement(reportViewer, {
                    delimiters: [
                        { left: '$$', right: '$$', display: true },
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
                const tickers = Array.from(document.querySelectorAll('.macro-watchlist-body-instance .symbol-bold'))
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
                            vli_llm_type: "core",
                            snaptrade_settings: getSnaptradeSettings()
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
                                    const row = document.querySelector(`.macro-watchlist-body-instance tr td[data-ticker="${ticker}"]`)?.parentElement;
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
            if (typeof vliPollingEnabled !== 'undefined' && !vliPollingEnabled) return;
            console.log("[VLI_TRACE] " + new Date().toLocaleTimeString() + " - Starting poll check...");
            isPolling = true;
            try {
                // Cache-busting to prevent Chrome/Edge from freezing the telemetry stream
                const res = await fetch(`/api/vli/active-state?t=${Date.now()}`);
                const data = await res.json();
                if (window.VLI_DEBUG) console.log("[VLI_TRACE] " + new Date().toLocaleTimeString() + " - Poll data received successfully.");
                if (data.error) throw new Error(data.error);

                const syncBadge = document.getElementById('menu-sync-status');
                const syncDot = document.getElementById('server-status-dot');
                if (syncBadge && syncDot) {
                    syncBadge.innerText = "Connected";
                    const toggleBtn = document.getElementById('server-toggle-btn');
                    if(toggleBtn) {
                        toggleBtn.style.background = "rgba(16, 185, 129, 0.1)";
                        toggleBtn.style.borderColor = "rgba(16, 185, 129, 0.3)";
                        toggleBtn.style.color = "var(--emerald-green)";
                        syncDot.style.backgroundColor = "var(--emerald-green)";
                        toggleBtn.style.opacity = "1";
                    }
                    const restartBtn = document.querySelector('button[title="Restart Server"]');
                    if(restartBtn) {
                        restartBtn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg> Restart`;
                        restartBtn.style.opacity = "1";
                        restartBtn.style.pointerEvents = "auto";
                    }
                }
                document.querySelectorAll('.live-badge').forEach(b => {
                    b.style.display = 'none';
                });
                
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
                renderScannerResults(data);
                renderShieldResults(data);

                // --- CHAT PERSISTENCE SYNC ---
                if (data.chat_history && Array.isArray(data.chat_history)) {
                    const msgBox = document.getElementById('chat-messages');
                    if (msgBox) {
                        // [SELF-HEALING] If DOM is empty but history exists, reset pointer (handles refresh)
                        const domMessageCount = msgBox.querySelectorAll('.msg').length;
                        if (domMessageCount === 0 && data.chat_history.length > 0) {
                            if (window.VLI_DEBUG) console.log("[VLI_SYNC] State Mismatch: DOM empty but history exists. Resetting sync pointer.");
                            vliChatSyncPointer = 0;
                        }
                        
                        // [SERVER REBOOT HEALING] If backend memory wiped, reset our pointer and DOM
                        if (data.chat_history.length < vliChatSyncPointer) {
                            console.warn(`[VLI_SYNC] Server Reboot Detected! Backend length (${data.chat_history.length}) < Local Pointer (${vliChatSyncPointer}). Resegmenting.`);
                            msgBox.innerHTML = ''; // Wipe orphaned messages
                            vliChatSyncPointer = 0;
                        }

                        if (window.VLI_DEBUG && data.chat_history.length > vliChatSyncPointer) {
                            console.log(`[VLI_SYNC] New history detected. Local Pointer: ${vliChatSyncPointer}, Server History: ${data.chat_history.length}`);
                        }
                        
                        for (let i = vliChatSyncPointer; i < data.chat_history.length; i++) {
                            const msg = data.chat_history[i];
                            vliAppendMessage(msgBox, msg);
                            vliChatSyncPointer++;
                        }
                    }
                }

                if (data.session_config && data.session_config.active_strategy) {
                    const strategy = data.session_config.active_strategy.toUpperCase();
                    // [REMOVED] Logic that overwrites scanner-filter dropdowns across all windows
                    // This allows individual windows to maintain their own filter state (e.g. one for Sortino, one for Core)
                }

                bc.postMessage({ type: 'STATE_UPDATE', state: data });
                if (window.VLI_DEBUG) console.log("[VLI_ORCHESTRA] Master Broadcast Sent.");

                // Status already updated above

            } catch (e) {
                console.error("VLI Poll Error:", e);
                const syncBadge = document.getElementById('menu-sync-status');
                const syncDot = document.getElementById('server-status-dot');
                if (syncBadge && syncDot) {
                    syncBadge.innerText = "Offline";
                    const toggleBtn = document.getElementById('server-toggle-btn');
                    if(toggleBtn) {
                        toggleBtn.style.background = "rgba(225, 29, 72, 0.1)";
                        toggleBtn.style.borderColor = "rgba(225, 29, 72, 0.3)";
                        toggleBtn.style.color = "var(--ruby-red)";
                        syncDot.style.backgroundColor = "var(--ruby-red)";
                    }
                }
                document.querySelectorAll('.live-badge').forEach(b => {
                    b.style.display = 'none';
                });
            } finally {
                isPolling = false;
            }
        }

        // --- HIGHLIGHT TRACKING STATE ---
        let previousSwordSymbols = new Set();
        let previousShieldSymbols = new Set();
        // [UX] Tracking for symbols currently being refreshed (Map of symbol -> requestTime)
        window.vliRefreshingSymbols = new Map();
        window.vliNewSymbols = window.vliNewSymbols || new Set();
        window.vliNewShieldSymbols = window.vliNewShieldSymbols || new Set();
        
        // [UX] Helper to update scanner row and macro row visual states immediately
        function updateScannerRefreshUI() {
            document.querySelectorAll('.scanner-res-row').forEach(tr => {
                const symbolTd = tr.querySelector('td:first-child');
                if (!symbolTd) return;
                const symbol = symbolTd.innerText.trim().toUpperCase();
                const isRefreshing = window.vliRefreshingSymbols.has(symbol);
                if (isRefreshing) {
                    tr.style.opacity = '1';
                    tr.style.filter = 'none';
                    Array.from(tr.children).forEach((td, idx) => {
                        if (idx !== tr.children.length - 1) {
                            td.style.opacity = '0.3';
                            td.style.filter = 'grayscale(1)';
                        }
                    });
                    tr.style.pointerEvents = 'none';
                } else {
                    tr.style.opacity = '1';
                    tr.style.filter = 'none';
                    Array.from(tr.children).forEach(td => {
                        td.style.opacity = '1';
                        td.style.filter = 'none';
                    });
                    tr.style.pointerEvents = 'auto';
                }
            });
            document.querySelectorAll('.macro-watchlist-body-instance tr').forEach(tr => {
                const symbolTd = tr.querySelector('td:nth-child(1)');
                if (!symbolTd || !symbolTd.dataset.ticker) return;
                const symbol = symbolTd.dataset.ticker.toUpperCase();
                const isRefreshing = window.vliRefreshingSymbols.has(symbol);
                if (isRefreshing) {
                    tr.style.opacity = '1';
                    tr.style.filter = 'none';
                    Array.from(tr.children).forEach((td, idx) => {
                        if (idx !== tr.children.length - 1) {
                            td.style.opacity = '0.3';
                            td.style.filter = 'grayscale(1)';
                        }
                    });
                    tr.style.pointerEvents = 'none';
                } else {
                    tr.style.opacity = '1';
                    tr.style.filter = 'none';
                    Array.from(tr.children).forEach(td => {
                        td.style.opacity = '1';
                        td.style.filter = 'none';
                    });
                    tr.style.pointerEvents = 'auto';
                }
            });
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

                    const metaObj = row.length >= 7 ? row[6] : {};
                    const hasReport = metaObj.has_report || false;

                    let sortinoColor = '#ff4444';
                    if (sortino >= 2.0) sortinoColor = '#00ff88';
                    else if (sortino >= 1.0) sortinoColor = '#ff9900';

                    let color = '#fff';
                    if (window.lastMacroWatchlistState[ticker]) {
                        const lastPrice = window.lastMacroWatchlistState[ticker].price;
                        if (priceNum > lastPrice) color = 'var(--price-up)';
                        else if (priceNum < lastPrice) color = 'var(--price-down)';
                    }
                    
                    function getMacroRowBackground(t, val) {
                        if (t === '^TNX') {
                            if (val >= 4.5) return 'rgba(255, 20, 20, 0.4)'; // Neon Red
                            if (val >= 4.3) return 'rgba(255, 165, 0, 0.4)'; // Clear Orange
                            if (val >= 4.0) return 'rgba(255, 230, 0, 0.35)'; // Bright Yellow
                            return 'rgba(0, 255, 100, 0.3)'; // Mint Green
                        }
                        if (t === '^VIX') {
                            if (val >= 25) return 'rgba(255, 20, 20, 0.4)';
                            if (val >= 20) return 'rgba(255, 165, 0, 0.4)';
                            if (val >= 15) return 'rgba(255, 230, 0, 0.35)';
                            return 'rgba(0, 255, 100, 0.3)';
                        }
                        if (t === 'DX-Y.NYB' || t === 'DXY') {
                            if (val >= 106.0) return 'rgba(255, 20, 20, 0.4)';
                            if (val >= 104.0) return 'rgba(255, 165, 0, 0.4)';
                            if (val >= 102.0) return 'rgba(255, 230, 0, 0.35)';
                            return 'rgba(0, 255, 100, 0.3)';
                        }
                        return 'transparent';
                    }
                    
                    const rowBg = getMacroRowBackground(ticker, priceNum);
                    
                    const mwTime = mw.timestamp ? new Date(mw.timestamp).getTime() : 0;
                    const reportTime = metaObj.updated_at ? new Date(metaObj.updated_at).getTime() : 0;
                    const dataTime = Math.max(mwTime, reportTime);
                    
                    const requestTime = window.vliRefreshingSymbols.get(ticker);
                    if (requestTime) {
                        if (dataTime > requestTime) {
                            console.log(`[VLI_UX] Macro Symbol ${ticker} verified fresh. Restoring formatting.`);
                            window.vliRefreshingSymbols.delete(ticker);
                        } else if (Date.now() - requestTime > 60000) {
                            console.log(`[VLI_UX] Macro Symbol ${ticker} refresh timed out.`);
                            window.vliRefreshingSymbols.delete(ticker);
                        }
                    }
                    
                    const isRefreshing = window.vliRefreshingSymbols.has(ticker);
                    const tr = document.createElement('tr');
                    tr.style.fontSize = '14px';
                    tr.style.cursor = 'pointer';
                    tr.style.transition = 'background 0.3s ease, opacity 0.5s ease, filter 0.5s ease';
                    tr.style.background = rowBg;
                    
                    if (isRefreshing) {
                        tr.style.pointerEvents = 'none';
                    }

                    tr.onmouseenter = () => {
                        tr.style.background = 'rgba(255,255,255,0.05)';
                    };
                    tr.onmouseleave = () => {
                        tr.style.background = rowBg;
                    };
                    tr.onclick = () => insertCardIdIntoChat(`analyze ${ticker}`);

                    tr.innerHTML = `
                        <td class="symbol-bold" style="padding: 6px 0; vertical-align: middle; max-width: 110px;" data-ticker="${ticker}">
                            <div style="font-size: 11px; color: var(--text-muted); line-height: 1; margin-bottom: 2px; white-space: nowrap; overflow: hidden; text-overflow: ellipsis;">${label}</div>
                            <div style="line-height: 1; display: flex; align-items: center; gap: 4px;">
                                ${ticker}
                            </div>
                        </td>
                        <td class="val-mono" style="color: ${color}; transition: color 0.5s ease; padding: 6px 0; vertical-align: middle;">${priceDisplay}</td>
                        <td class="val-mono" style="color: ${pctChange >= 0 ? 'var(--price-up)' : 'var(--price-down)'}; padding: 6px 0; vertical-align: middle;">
                            ${pctChange >= 0 ? '▲' : '▼'} ${Math.abs(pctChange).toFixed(2)}%
                        </td>
                        <td class="val-mono" style="color: ${sortinoColor}; font-weight: 700; padding: 6px 0; vertical-align: middle;">${sortino}</td>
                        <td style="padding: 6px 0; vertical-align: middle;">
                            <div style="display: flex; align-items: center; justify-content: flex-end; gap: 16px; padding-right: 16px;">
                                ${drawSparkline(sparklineObj.value, ticker)}
                                <div style="width: 24px; display: flex; justify-content: center;">
                                    ${isRefreshing ? 
                                    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--amber-gold)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" title="Retrieval in Progress"><circle cx="12" cy="14" r="8"></circle><polyline points="12 10 12 14 14 16"></polyline><line x1="10" y1="2" x2="14" y2="2"></line><line x1="12" y1="2" x2="12" y2="6"></line></svg>` 
                                    : 
                                    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: ${hasReport ? 'var(--emerald-green)' : 'rgba(255,255,255,0.2)'}; cursor: pointer;" onclick="event.stopPropagation(); window.openReportModal('${ticker}')" title="Structural Analysis"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`}
                                </div>
                            </div>
                        </td>
                    `;
                    if (isRefreshing) {
                        Array.from(tr.children).forEach((td, idx) => {
                            if (idx !== tr.children.length - 1) {
                                td.style.opacity = '0.3';
                                td.style.filter = 'grayscale(1)';
                            }
                        });
                    }
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

        // 1c. Scanner State & SSE Logic
        let scannerEventSource = null;
        window.vliNewSymbols = window.vliNewSymbols || new Set();
        let activeScannerCandidates = []; 
        window.vliNewSymbols.clear();
        
        // Initialize scanner candidates from the backend bunker on startup
        fetch('/api/scanner/bunker')
            .then(r => r.json())
            .then(d => {
                console.log("BUNKER FETCH RESOLVED. success:", d.status, "data length:", d.data ? d.data.length : 0);
                if(d.status === 'success' && d.data) {
                    activeScannerCandidates = d.data;
                    console.log("CALLING updateScannerResultsUI");
                    updateScannerResultsUI();
                }
            })
            .catch(e => console.log('Failed to fetch initial scanner bunker', e));
        
        // GLOBAL Telemetry Stream
        const globalTelemetrySource = new EventSource('/api/telemetry/stream');
        globalTelemetrySource.onmessage = (e) => {
            const data = JSON.parse(e.data);
            if (data.type === 'telemetry') {
                appendSystemLog(data.msg, 'rgba(255, 255, 255, 0.9)');
            }
        };
        
        // Auto-refresh pollers removed in favor of unified VLI poll cycle

        function startScanner() {
            if (isScannerRunning) return;
            isScannerRunning = true;
            const btn = document.getElementById('scanner-action-btn');
            const btnText = document.getElementById('scanner-btn-text');
            
            btn.classList.add('stop-state');
            btnText.innerText = 'STOP SCAN';
            
            console.log("[VLI_SCANNER] Initializing institutional scan via SSE...");
            activeScannerCandidates = []; window.vliNewSymbols.clear();
            
            // Append initial system log to telemetry
            appendSystemLog("INITIATING MARKET-WIDE SNIPER TRAWL...");

            fetch('/api/vli/action-plan', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    text: "RUN MORNING SCAN",
                    direct_mode: true,
                    raw_data_mode: false,
                    background_synthesis: true,
                    thread_id: "vli-" + Date.now(),
                    snaptrade_settings: getSnaptradeSettings()
                })
            });
        }

        function initScannerSSE() {
            if (scannerEventSource) {
                console.warn("[VLI_SCANNER] Scanner already active. Terminating previous session.");
                stopScanner();
            }
            
            window._vliIsScanning = true;
            updateScannerResultsUI();
            
            scannerEventSource = new EventSource('/api/scanner/stream');

            scannerEventSource.onmessage = (e) => {
                const data = JSON.parse(e.data);
                if (data.type === 'telemetry') {
                    appendSystemLog(`[TELEMETRY] ${data.msg || data.message || 'Incoming pulse...'}`);
                    if (data.msg === 'Pipeline execution finished cleanly.') {
                        console.log("[VLI_SCANNER] Pipeline finished gracefully. Closing EventSource.");
                        scannerEventSource.close();
                        scannerEventSource = null;
                        appendSystemLog("--- SCAN COMPLETED ---", 'var(--emerald-green)');
                        window._vliIsScanning = false;
                        updateScannerResultsUI();
                    }
                } else if (data.type === 'phase0') {
                    appendSystemLog(`[PHASE 0] Discovery Pool: ${data.msg || data.message || 'Processing raw universe...'}`, 'var(--cobalt-blue)');
                } else if (data.type === 'phase1') {
                    appendSystemLog(`[PHASE 1] Structural Verify: ${data.msg || data.message || 'Applying Sortino filters...'}`, 'rgba(0, 170, 255, 0.7)');
                } else if (data.type === 'phase2') {
                    const candidates = data.data || data.candidates || [];
                    const existingSymbols = new Set(activeScannerCandidates.map(c => c.symbol));
                    const newCandidates = candidates.filter(c => !existingSymbols.has(c.symbol));
                    
                    newCandidates.forEach(c => window.vliNewSymbols.add(c.symbol));
                    activeScannerCandidates = [...activeScannerCandidates, ...newCandidates];
                    
                    newCandidates.forEach(c => {
                        appendSystemLog(`[SELECTED] ${c.symbol} (Score: ${c.score || c.sortino || 'N/A'}) - Passing Pulse Filter.`, 'var(--emerald-green)');
                    });
                    
                    updateScannerResultsUI();
                }
            };

            scannerEventSource.addEventListener('telemetry', (e) => {
                const data = JSON.parse(e.data);
                appendSystemLog(`[TELEMETRY] ${data.msg || data.message}`, 'rgba(255, 255, 255, 0.7)');
            });

            scannerEventSource.addEventListener('phase0', (e) => {
                const data = JSON.parse(e.data);
                appendSystemLog(`[PHASE 0] Discovery Pool: ${data.msg || data.message || 'Processing raw universe...'}`, 'var(--cobalt-blue)');
            });

            scannerEventSource.addEventListener('phase1', (e) => {
                const data = JSON.parse(e.data);
                appendSystemLog(`[PHASE 1] Structural Verify: ${data.msg || data.message || 'Applying Sortino filters...'}`, 'rgba(0, 170, 255, 0.7)');
            });

            scannerEventSource.addEventListener('phase2', (e) => {
                const data = JSON.parse(e.data);
                const candidates = data.data || data.candidates || [];
                if (candidates && candidates.length > 0) {
                    // Filter duplicates and merge
                    const existingSymbols = new Set(activeScannerCandidates.map(c => c.symbol));
                    const newCandidates = candidates.filter(c => !existingSymbols.has(c.symbol));
                    
                    newCandidates.forEach(c => window.vliNewSymbols.add(c.symbol));
                    activeScannerCandidates = [...activeScannerCandidates, ...newCandidates];
                    
                    newCandidates.forEach(c => {
                        appendSystemLog(`[SELECTED] ${c.symbol} (Score: ${c.score || c.sortino || 'N/A'}) - Passing Pulse Filter.`, 'var(--emerald-green)');
                    });
                    
                    updateScannerResultsUI();
                }
            });

            scannerEventSource.onerror = (err) => {
                console.error("[VLI_SCANNER] SSE Error:", err);
                appendSystemLog("INTERNAL SERVER ERROR IN SCANNER PIPELINE.", 'var(--ruby-red)');
                stopScanner();
            };
        }

        function stopScanner() {
            window._vliIsScanning = false;
            if (scannerEventSource) {
                scannerEventSource.close();
                scannerEventSource = null;
                appendSystemLog("--- SCAN TERMINATED BY USER ---", 'var(--ruby-red)');
            }
            updateScannerResultsUI();
        }

        function toggleTrackSpy(cb) {
            const card = cb.closest('.card');
            if (!card) return;
            const instanceGuid = card.dataset.instanceGuid;
            
            if (!window.vliScannerTrackSpy) window.vliScannerTrackSpy = {};
            window.vliScannerTrackSpy[instanceGuid] = cb.checked;
            
            // Force re-render of local scanner results without refetching from backend
            updateScannerResultsUI();
        }

        function handleScannerTierChange(selectElement) {
            // Decoupled: Only refilter locally, do not trigger global backend rescans
            updateScannerResultsUI();
        }

        async function initScannerSettings() {
            try {
                const res = await fetch('/api/vli/scanner-settings');
                if (res.ok) {
                    const data = await res.json();
                    window._vliTrackSpy = data.track_spy;
                    document.querySelectorAll('.track-spy-cb').forEach(cb => cb.checked = data.track_spy);
                }
            } catch (e) {}
        }

        function appendSystemLog(msg, color = 'var(--cobalt-blue)') {
            document.querySelectorAll('.telemetry-body-instance').forEach(tBody => {
                const logContainer = tBody.closest('.terminal');
                const wasAtBottom = logContainer.scrollHeight - logContainer.scrollTop <= logContainer.clientHeight + 50;

                const line = document.createElement('div');
                line.style.borderBottom = '1px solid rgba(255, 255, 255, 0.02)';
                line.style.padding = '2px 0';
                line.innerHTML = `<span style="color: ${color}; font-weight: bold; opacity: 0.5;">[${new Date().toLocaleTimeString()}]</span> <span style="color: ${color}">${msg}</span>`;
                
                tBody.appendChild(line);

                if (wasAtBottom) {
                    logContainer.scrollTo({ top: logContainer.scrollHeight, behavior: 'smooth' });
                }
            });
        }

        function updateScannerResultsUI() {
            // Leverage existing function but with state
            renderScannerResults({
                scanner_results: {
                    pulse_mode: 'InstitutionalPulse',
                    candidates: activeScannerCandidates
                }
            });
        }

        // 1c. Scanner Results UI
        function renderScannerResults(data) {
            if (!data.scanner_results || !data.scanner_results.candidates) return;
            
            const allCandidates = data.scanner_results.candidates;

            // [NEW CANDIDATE TRACKING] Determine differential highlights across all tracked candidates
            const currentSymbols = new Set(allCandidates.map(c => c.symbol));
            if (previousSwordSymbols.size > 0) {
                currentSymbols.forEach(sym => {
                    if (!previousSwordSymbols.has(sym)) {
                        window.vliNewSymbols.add(sym);
                    }
                });
            }
            previousSwordSymbols = currentSymbols;

            const spyBenchmark = data.scanner_results.metadata?.spy_benchmark || 0.0;
            const res = { ...data.scanner_results, candidates: allCandidates };
            
            document.querySelectorAll('.card[data-type-guid="SCAN_RES"]').forEach(card => {
                let body = card.querySelector('.card-body');
                if (!body) {
                    console.warn("[VLI_UI_HEALING] SCAN_RES missing .card-body. Auto-injecting structure.");
                    body = document.createElement('div');
                    body.className = 'card-body';
                    body.style.display = 'flex';
                    body.style.flexDirection = 'column';
                    body.style.overflowY = 'hidden';
                    body.style.padding = '10px';
                    // Ensure the card correctly positions the newly injected body
                    body.style.height = 'calc(100% - 30px)'; // Account for header
                    card.appendChild(body);
                }
                
                // Add Focus Highlight (Removed aggressive zIndex override that caused z-index popping against UX placement)
                
                let table = body.querySelector('table');
                if (!table) {
                    body.innerHTML = `
                        <div style="font-size: 11px; margin-bottom: 12px; color: var(--text-muted); display: flex; justify-content: space-between; align-items: center;">
                            <div style="display:flex; gap: 8px; align-items: center;">
                                <select id="scan-filter-${card.dataset.instanceGuid}" class="vli-input" style="padding: 2px 4px; border: 1px solid var(--card-border); background: rgba(0,0,0,0.3); color: #fff; outline: none; border-radius: 3px;" onchange="handleScannerTierChange(this)">
                                    <option value="SNIPER" ${card.dataset.instanceGuid === 'scanner' ? 'selected' : ''}>Sortino Sniper</option>
                                    <option value="SHIELD" ${card.dataset.instanceGuid === 'shield' ? 'selected' : ''}>Apex Core Scan</option>
                                    <option value="SWORD">Apex Satellite Scan</option>
                                </select>
                            </div>
                            <div style="font-family: var(--font-mono); font-size: 10px;">Updated: <span id="sr-updated-at" style="color: var(--emerald-green); font-weight: 800;">${new Date().toLocaleTimeString()}</span></div>
                        </div>
                        <div style="flex-grow: 1; overflow-y: auto;">
                            <table class="macro-table ibkr-style-table scanner-table" style="width:100%; border-collapse: collapse; font-family: 'Inter', sans-serif; font-size: 11px;">
                                <thead>
                                    <tr style="border-bottom: 1px solid var(--card-border); color: var(--text-muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;">
                                        <th style="padding: 4px 2px; text-align: left;">SYMBOL</th>
                                        <th style="padding: 4px 2px; text-align: right;">PRICE</th>
                                        <th style="padding: 4px 2px; text-align: right;">CHANGE</th>
                                        <th style="padding: 4px 2px; text-align: right;">SORTINO</th>
                                        <th style="padding: 4px 2px; text-align: center;">GRADE</th>
                                    </tr>
                                </thead>
                                <tbody></tbody>
                            </table>
                        </div>
                        <div style="display: flex; justify-content: space-between; align-items: center; margin-top: 10px;">
                            <label style="display: flex; align-items: center; gap: 4px; color: var(--text-muted); cursor: pointer; font-size: 10px; font-weight: 600; text-transform: uppercase;" title="Filter by Relative Strength against S&P">
                                <input type="checkbox" class="track-spy-cb" onchange="toggleTrackSpy(this)" style="accent-color: var(--emerald-green); cursor: pointer;" ${window.vliScannerTrackSpy && window.vliScannerTrackSpy[card.dataset.instanceGuid] ? 'checked' : ''}> RS Filter
                            </label>
                            <button class="scanner-refresh-btn" onclick="let b=this.closest('.card-body'); b.querySelectorAll('tbody tr').forEach(r => r.style.opacity = '0.3'); fetch('/api/scanner/bunker').then(r=>r.json()).then(d=>{if(d.status==='success'){activeScannerCandidates=d.data;updateScannerResultsUI();}});" style="background: rgba(245, 158, 11, 0.1); border: 1px solid rgba(245, 158, 11, 0.3); color: #f59e0b; padding: 2px 8px; border-radius: 4px; cursor: pointer; font-size: 11px; font-weight: 600; display: flex; align-items: center; gap: 4px;" title="Refresh">
                                <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg>
                                Refresh
                            </button>
                        </div>
                    `;
                    table = body.querySelector('table');
                } else {
                    const timeEl = body.querySelector('#sr-updated-at');
                    if (timeEl) timeEl.innerText = new Date().toLocaleTimeString();
                    
                    const cb = body.querySelector('.track-spy-cb');
                    if (cb && typeof window._vliTrackSpy !== 'undefined') {
                        cb.checked = window._vliTrackSpy;
                    } else if (cb) {
                        cb.checked = false; // Default off
                    }
                }
                
                const tbody = table.querySelector('tbody');
                tbody.innerHTML = '';
                
                const filterEl = body.querySelector('#scan-filter-' + card.dataset.instanceGuid);
                const activeFilter = filterEl ? filterEl.value : 'SHIELD';
                
                let filteredCandidates = res.candidates.filter(c => {
                    if (activeFilter === 'SNIPER' && c.tier === 'SNIPER') return true;
                    if (activeFilter === 'SHIELD' && c.tier === 'SHIELD') return true;
                    if (activeFilter === 'SWORD' && (c.tier === 'SWORD' || !c.tier)) return true;
                    return false;
                });
                
                if (window.vliScannerTrackSpy && window.vliScannerTrackSpy[card.dataset.instanceGuid]) {
                    filteredCandidates = filteredCandidates.filter(c => {
                        const sym_perf_3m = parseFloat(c.perf_3m) || 0.0;
                        return sym_perf_3m >= (spyBenchmark + 15.0);
                    });
                }
                
                if (filteredCandidates.length === 0) {
                    const statusText = window._vliIsScanning ? "Scanning..." : "Empty List: No candidates passed institutional criteria.";
                    const styleMod = window._vliIsScanning ? "color: var(--cobalt-blue); font-weight: bold; letter-spacing: 1px;" : "color: var(--text-muted); font-style: italic;";
                    tbody.innerHTML = `
                        <tr style="border: none;">
                            <td colspan="5" style="text-align: center; padding: 30px 10px; font-size: 12px; ${styleMod}">${statusText}</td>
                        </tr>
                    `;
                }

                // [FRONTEND CURVE GRADING] Re-grade the elite list relative to each other using sortino
                if (filteredCandidates.length > 0) {
                    const validCandidates = filteredCandidates.filter(c => c.sortino !== undefined && c.sortino !== null);
                    if (validCandidates.length > 0) {
                        const maxPower = Math.max(...validCandidates.map(c => c.sortino));
                        const minPower = Math.min(...validCandidates.map(c => c.sortino));
                        
                        filteredCandidates.forEach(c => {
                            if (c.sortino === undefined || c.sortino === null) return;
                            
                            let percentile = 1.0;
                            if (maxPower > minPower) {
                                percentile = (c.sortino - minPower) / (maxPower - minPower);
                            }
                            
                            // 40-100 UI visual sweep. S tier requires >= 95 (Top 8%)
                            c.heat_score = Math.floor(40 + (percentile * 60));
                            
                            if (c.heat_score >= 95) c.grade = 'S';
                            else if (c.heat_score >= 90) c.grade = 'A+';
                            else if (c.heat_score >= 82) c.grade = 'A';
                            else if (c.heat_score >= 75) c.grade = 'B+';
                            else if (c.heat_score >= 65) c.grade = 'B';
                            else if (c.heat_score >= 58) c.grade = 'C+';
                            else if (c.heat_score >= 50) c.grade = 'C';
                            else if (c.heat_score >= 35) c.grade = 'D';
                            else c.grade = 'F';
                        });
                    }
                }

                // Autonomously sort candidates from strongest to weakest using the internal heat score
                filteredCandidates.sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0));

                filteredCandidates.forEach(c => {
                    let gradeColor = 'var(--text-muted)';
                    let gradeBg = 'rgba(255,255,255,0.05)';
                    let gradeBorder = 'rgba(255,255,255,0.2)';

                    if (c.grade === 'S') { gradeColor = '#ffaa00'; gradeBg = 'rgba(255, 170, 0, 0.1)'; gradeBorder = 'rgba(255, 170, 0, 0.3)'; }
                    else if (c.grade === 'A+' || c.grade === 'A') { gradeColor = '#d866ff'; gradeBg = 'rgba(216, 102, 255, 0.1)'; gradeBorder = 'rgba(216, 102, 255, 0.3)'; }
                    else if (c.grade === 'B+' || c.grade === 'B') { gradeColor = '#00aaff'; gradeBg = 'rgba(0, 170, 255, 0.1)'; gradeBorder = 'rgba(0, 170, 255, 0.3)'; }
                    else if (c.grade === 'C+' || c.grade === 'C') { gradeColor = '#3fb950'; gradeBg = 'rgba(63, 185, 80, 0.1)'; gradeBorder = 'rgba(63, 185, 80, 0.3)'; }
                    else { gradeColor = 'var(--ruby-red)'; gradeBg = 'rgba(248, 81, 73, 0.1)'; gradeBorder = 'rgba(248, 81, 73, 0.3)'; }
                    

                    
                    c.isNew = window.vliNewSymbols.has(c.symbol);
                    const tr = document.createElement('tr');
                    tr.style.cursor = 'pointer';
                    tr.className = c.isNew ? 'scanner-res-row new-candidate-highlight' : 'scanner-res-row';
                    tr.style.transition = 'background 0.3s ease, opacity 0.5s ease, filter 0.5s ease';
                    
                    // [UX: TEMPORAL VERIFICATION] 
                    // Auto-restore ONLY if we see a timestamp that is newer than our request time.
                    const requestTime = window.vliRefreshingSymbols.get(c.symbol);
                    if (requestTime) {
                        const dataTime = c.updated_at ? new Date(c.updated_at).getTime() : 0;
                        if (dataTime > requestTime) {
                            console.log(`[VLI_UX] Symbol ${c.symbol} refetched and verified fresh. Restoring formatting.`);
                            window.vliRefreshingSymbols.delete(c.symbol);
                        } else if (Date.now() - requestTime > 60000) {
                            console.log(`[VLI_UX] Symbol ${c.symbol} refresh cancelled or interrupted.`);
                            window.vliRefreshingSymbols.delete(c.symbol);
                        }
                    }

                    const isRefreshing = window.vliRefreshingSymbols.has(c.symbol);
                    if (isRefreshing) {
                        tr.style.pointerEvents = 'none';
                    } else {
                        tr.style.pointerEvents = 'auto';
                    }
                    

                    
                    tr.onmouseenter = () => {
                        if (window.vliNewSymbols.has(c.symbol)) {
                            tr.classList.remove('new-candidate-highlight');
                            window.vliNewSymbols.delete(c.symbol);
                            c.isNew = false;
                        }
                    };
                    tr.onmouseleave = () => {};
                    
                    tr.onclick = () => insertCardIdIntoChat(`analyze ${c.symbol}`);
                    
                    const changeVal = parseFloat(c.change || c.gap || 0);
                    const changeColor = changeVal >= 0 ? 'var(--price-up)' : 'var(--price-down)';
                    
                    tr.innerHTML = `
                        <td style="padding: 4px 2px; color: #fff; font-weight: 700;">${c.symbol}</td>
                        <td style="padding: 4px 2px; text-align: right; font-family: var(--font-mono); color: #fff;">$${parseFloat(c.price || 0).toFixed(2)}</td>
                        <td style="padding: 4px 2px; text-align: right; font-family: var(--font-mono); color: ${changeColor};">${changeVal >= 0 ? '+' : ''}${changeVal.toFixed(2)}%</td>
                        <td style="padding: 4px 2px; text-align: right; font-family: var(--font-mono); color: ${(parseFloat(c.sortino || c.score || 0) < 0) ? 'var(--ruby-red)' : 'var(--emerald-green)'}; font-weight: 800;">${parseFloat(c.sortino || c.score || 0).toFixed(2)}</td>
                        <td style="padding: 4px 2px;">
                            <div style="display: flex; align-items: center; justify-content: flex-end;">
                                <span style="display: inline-block; width: 32px; text-align: center; background: ${gradeBg}; color: ${gradeColor}; padding: 2px 0; border-radius: 4px; font-size: 10px; font-weight: 800; border: 1px solid ${gradeBorder};">${c.grade || 'F'}</span>
                                <div style="width: 24px; display: flex; justify-content: flex-end;">
                                    ${isRefreshing ? 
                                    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--amber-gold)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" title="Retrieval in Progress"><circle cx="12" cy="14" r="8"></circle><polyline points="12 10 12 14 14 16"></polyline><line x1="10" y1="2" x2="14" y2="2"></line><line x1="12" y1="2" x2="12" y2="6"></line></svg>` 
                                    : 
                                    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: ${c.has_report ? 'var(--emerald-green)' : 'rgba(255,255,255,0.2)'}; cursor: pointer;" onclick="event.stopPropagation(); window.openReportModal('${c.symbol}')" title="Structural Analysis"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`}
                                </div>
                            </div>
                        </td>
                    `;
                    
                    if (isRefreshing) {
                        Array.from(tr.children).forEach((td, idx) => {
                            if (idx !== tr.children.length - 1) {
                                td.style.opacity = '0.3';
                                td.style.filter = 'grayscale(1)';
                            }
                        });
                    }
                    
                    tbody.appendChild(tr);
                });
            });
        }

        // 2. Telemetry
        function renderTelemetry(data) {
            document.querySelectorAll('.telemetry-body-instance').forEach(tBody => {
                const logContainer = tBody.closest('.terminal');
                const wasAtBottom = logContainer.scrollHeight - logContainer.scrollTop <= logContainer.clientHeight + 50;

                const newTelemetry = data.telemetry_tail || "";
                if (tBody.dataset.lastContent !== newTelemetry) {
                    let safeTelemetry = newTelemetry.replace(/\\n/g, '\n');
                    const leakKeywords = ["# SECURITY OVERRIDE", "APEX 500 SYSTEM", "USER IDENTITY: DAVE", "OPERATIONAL MANDATE"];
                    if (leakKeywords.some(k => safeTelemetry.toUpperCase().includes(k))) {
                        safeTelemetry = "** [VLI_MONITOR]: TECHNICAL STATE LEAKAGE SUPPRESSED.**";
                    }
                    
                    // Color code task prefixes
                    let lines = safeTelemetry.split('\n');
                    let processedLines = lines.map(line => {
                        let match = line.match(/^(\[\d{2}:\d{2}:\d{2}\]\s*(?:.*?(?:\*\*|||||||)\s*)?)?\[([A-Z0-9_ -]+)\](.*)/i);
                        if (match) {
                            let prefix = match[1] || '';
                            let taskName = match[2];
                            let rest = match[3];
                            
                            let color = '#8b949e';
                            let tUpper = taskName.toUpperCase();
                            if (tUpper.includes('SPINE') || tUpper.includes('ROUTER')) color = '#58a6ff'; // Blue
                            else if (tUpper.includes('NEWS') || tUpper.includes('BACKGROUND')) color = '#ff7b72'; // Red
                            else if (tUpper.includes('FINANCE') || tUpper.includes('QUOTE')) color = '#3fb950'; // Green
                            else if (tUpper.includes('ORCHESTRATOR') || tUpper.includes('COORDINATOR')) color = '#d2a8ff'; // Purple
                            else if (tUpper.includes('WORKER') || tUpper.includes('ANALYST')) color = '#f0ad4e'; // Yellow
                            else if (tUpper.includes('TELEMETRY')) color = '#a5d6ff'; // Light Blue
                            else if (tUpper.includes('TV_SYNC')) color = '#6e7681'; // Mid-Gray
                            
                            return `${prefix}<span style="color:${color}; font-weight:bold;">[${taskName}]</span>${rest}`;
                        }
                        return line;
                    });
                    safeTelemetry = processedLines.join('\n');

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
                if (reportViewer.dataset.isStatic === "true") return;
                if (data.async_report && reportViewer.dataset.lastReport !== data.async_report) {
                    let safeReport = data.async_report;
                    const leakKeywords = ["# SECURITY OVERRIDE", "APEX 500 SYSTEM", "USER IDENTITY: DAVE", "OPERATIONAL MANDATE"];
                    if (leakKeywords.some(k => safeReport.toUpperCase().includes(k))) {
                        reportViewer.dataset.lastReport = data.async_report;
                    } else {
                        reportViewer.innerHTML = `<div class="msg-ai" style="padding: 15px;">${applyStatusFormatting(marked.parse(safeReport))}</div>`;
                        reportViewer.dataset.lastReport = data.async_report;
                        reportViewer.scrollTop = 0;
                        try {
                            renderMathInElement(reportViewer, {
                                delimiters: [
                                    { left: '$$', right: '$$', display: true },
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
            msgBox.appendChild(activeTypingIndicator);
            msgBox.scrollTop = msgBox.scrollHeight;
        }

        function hideTypingIndicator() {
            if (activeTypingIndicator) {
                activeTypingIndicator.classList.add('fade-out');
                const target = activeTypingIndicator;
                setTimeout(() => { if (target.parentNode) target.remove(); }, 500);
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

            // NEW: Telemetry Clear Interceptor
            const clearMatch = rawText.match(/^clear\s+(scheduler|system|[A-Z0-9-]+)\s+telemetry$/i);
            if (clearMatch && !isRegen) {
                const target = clearMatch[1].toUpperCase();
                input.value = '';
                
                let cleared = false;
                if (target === 'SCHEDULER') {
                    // Clear the scheduler telemetry panel content and the backend log file
                    const instances = document.querySelectorAll('.chat-messages[id^="scheduler-log-messages-"]');
                    instances.forEach(el => {
                        el.innerHTML = '<div style="color: var(--text-muted); padding: 10px;">Telemetry scrubbed.</div>';
                        cleared = true;
                    });
                    // Also fire a reset to backend to wipe the file
                    originalFetch('/api/vli/reset_scheduler_logs', {method: 'POST'}).catch(()=>{});
                } else if (target === 'SYSTEM') {
                    // System telemetry is the main bottom terminal
                    const el = document.getElementById('telemetry-body');
                    if (el) {
                        el.innerHTML = '<div class="log-entry">SYSTEM TELEMETRY SCRUBBED</div>';
                        el.dataset.lastContent = "";
                        cleared = true;
                    }
                } else {
                    // UX_ID targets a specific panel of type VLI_TELEMETRY
                    const el = document.getElementById(`telemetry-body-${target}`);
                    if (el) {
                        el.innerHTML = '';
                        el.dataset.lastContent = "";
                        cleared = true;
                    } else if (window.UXManager && window.UXManager.instances[`win-${target}`]) {
                        const card = window.UXManager.instances[`win-${target}`];
                        if (card.dataset.typeGuid === 'VLI_TELEMETRY') {
                            const innerEl = card.querySelector('.telemetry-body-instance');
                            if (innerEl) {
                                innerEl.innerHTML = '';
                                innerEl.dataset.lastContent = "";
                                cleared = true;
                            }
                        }
                    }
                }
                
                if (cleared) {
                    vliAppendMessage(msgBox, {role: 'system', content: `Telemetry scrubbed for target: ${target}.`});
                } else {
                    vliAppendMessage(msgBox, {role: 'system', content: `Telemetry target not found or not a valid telemetry window: ${target}.`});
                }
                
                chatHistory.push(rawText);
                historyIndex = chatHistory.length;
                return; // Do not send to backend
            }

            if (!isRegen) {
                // Push to history
                chatHistory.push(rawText);
                historyIndex = chatHistory.length;
                input.value = '';

                // Standardized User Rendering
                vliAppendMessage(msgBox, {role: 'user', content: rawText, timestamp: new Date().toLocaleTimeString('en-US', {hour12:false})});
                vliChatSyncPointer++;
            }

            const btn = document.getElementById('send-stop-btn');
            btn.innerText = "";
            btn.classList.add('processing');
            isProcessing = true;

            if (!isRegen) {
                showTypingIndicator();
            } else {
                regenTargetAiMsg.innerHTML = '<div class="typing-indicator"></div>';
            }

            try {
                let requestText = rawText;

                if (isProcessing) {
                    if (/^\s*(run|start|generate)\s+(market\s+|full\s+)?scan\s*[.!?]?\s*$/i.test(requestText)) {
                        console.log("[VLI_TRACE] Intercepting Market Scan Command (Isolation Block)...");
                        initScannerSSE();
                        
                        const sysMsg = document.createElement('div');
                        sysMsg.className = 'msg msg-ai';
                        sysMsg.style.borderColor = 'var(--emerald-green)';
                        sysMsg.innerHTML = "<strong>SYSTEM:</strong> Initializing Institutional Market Scan. Monitoring Telemetry (TM) and Scanner Results (SR) cards for live findings.";
                        msgBox.appendChild(sysMsg);
                        
                        btn.classList.remove('processing');
                        btn.innerText = "➤";
                        isProcessing = false;
                        msgBox.scrollTop = msgBox.scrollHeight;
                        return;
                    } else if (/^\s*(stop|abort|kill)\s+(market\s+)?scan\s*[.!?]?\s*$/i.test(requestText)) {
                        console.log("[VLI_TRACE] Intercepting Stop Scan Command (Isolation Block)...");
                        stopScanner();
                        
                        btn.classList.remove('processing');
                        btn.innerText = "➤";
                        isProcessing = false;
                        return;
                    } else if (requestText.toUpperCase().startsWith("REFRESH") || requestText.toUpperCase().startsWith("UPDATE") || requestText.toUpperCase().startsWith("REGENERATE") || requestText.toUpperCase().startsWith("ANALYZE")) {
                        let parts = requestText.split(/\s+/);
                        let cmd = parts[0].toUpperCase();
                        let target = parts.length > 1 ? parts[1].toUpperCase() : "ALL";

                        if (target === "DAILY" || target === "DAILIES") {
                            console.log("[VLI_UX] Batch refresh initiated. Targeting all visible scanner symbols.");
                            const now = Date.now();
                            document.querySelectorAll('.scanner-res-row td:first-child').forEach(td => {
                                let sym = td.innerText.trim().toUpperCase();
                                if (sym) window.vliRefreshingSymbols.set(sym, now);
                            });
                            updateScannerRefreshUI();
                        } else if (target === "ALL" && cmd === "REGENERATE") {
                            console.log("[VLI_UX] Global regenerate initiated. Targeting all visible symbols.");
                            const now = Date.now();
                            document.querySelectorAll('.scanner-res-row td:first-child').forEach(td => {
                                let sym = td.innerText.trim().toUpperCase();
                                if (sym) window.vliRefreshingSymbols.set(sym, now);
                            });
                            document.querySelectorAll('.macro-watchlist-body-instance tr').forEach(tr => {
                                let symTd = tr.querySelector('td:nth-child(1)');
                                if (symTd && symTd.dataset.ticker) {
                                    window.vliRefreshingSymbols.set(symTd.dataset.ticker.toUpperCase(), now);
                                }
                            });
                            updateScannerRefreshUI();
                        } else if (target && target.length <= 6 && !["CI", "TM", "WL", "AR", "CHAT", "ALL"].includes(target)) {
                            console.log(`[VLI_UX] Targeting symbol for refresh: ${target}`);
                            window.vliRefreshingSymbols.set(target, Date.now());
                            updateScannerRefreshUI();
                        }

                        if (cmd === "REFRESH" && ["CI", "TM", "WL", "AR", "CHAT", "ALL"].includes(target)) {
                            fetch('/api/vli/refresh-card', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify({ card_id: target }) });
                            if (target === "ALL" || target === "CHAT" || target === "CI") resetVLI();
                            btn.classList.remove('processing');
                            btn.innerText = "➤";
                            isProcessing = false;
                            return;
                        }
                        // Continue to standard action-plan for other refresh types
                        console.log("[VLI_TRACE] Forwarding REGENERATE command to backend: " + rawText);
                        const startTime = performance.now();
                        const res = await fetch('/api/vli/action-plan', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                text: rawText,
                                direct_mode: directMode,
                                raw_data_mode: false,
                                background_synthesis: asyncMode,
                                thread_id: lastVliThreadId,
                                snaptrade_settings: getSnaptradeSettings()
                            })
                        });
                        const data = await res.json();
                        if (data.thread_id) lastVliThreadId = data.thread_id;
                        
                        if (isProcessing) {
                            if (data.metadata && data.metadata.action === "OPEN_REPORT") {
                                if (data.metadata.artifact_type === "REPORT") {
                                    window.openReportModal(data.metadata.symbol);
                                }
                                const aiMsg = document.createElement('div');
                                aiMsg.className = 'msg msg-ai';
                                aiMsg.style.borderColor = 'var(--emerald-green)';
                                aiMsg.innerHTML = applyStatusFormatting(`**SYSTEM**: Opening ${data.metadata.artifact_type} UX Panel for **${data.metadata.symbol}**.`);
                                msgBox.appendChild(aiMsg);
                                vliChatSyncPointer++;
                                msgBox.scrollTop = msgBox.scrollHeight;
                            } else if (data.metadata && data.metadata.action === "OPEN_CARD") {
                                UXManager.createCard(data.metadata.card_type);
                                const aiMsg = document.createElement('div');
                                aiMsg.className = 'msg msg-ai';
                                aiMsg.innerHTML = applyStatusFormatting(`**SYSTEM**: Spawned UX Module **${data.metadata.card_type}**.`);
                                msgBox.appendChild(aiMsg);
                                vliChatSyncPointer++;
                                msgBox.scrollTop = msgBox.scrollHeight;
                            } else if (data.metadata && data.metadata.action === "CLOSE_CARD") {
                                if (data.metadata.card_id === "ALL") {
                                    Object.keys(UXManager.instances).forEach(id => UXManager.removeCard(id));
                                } else {
                                    const cards = Object.entries(UXManager.instances).filter(([id, card]) => card.dataset.badge === data.metadata.card_id.toUpperCase());
                                    cards.forEach(([id, card]) => UXManager.removeCard(id));
                                }
                                const aiMsg = document.createElement('div');
                                aiMsg.className = 'msg msg-ai';
                                aiMsg.innerHTML = applyStatusFormatting(`**SYSTEM**: Destroyed UX Module **${data.metadata.card_id}**.`);
                                msgBox.appendChild(aiMsg);
                                vliChatSyncPointer++;
                                msgBox.scrollTop = msgBox.scrollHeight;
                            } else {
                                const responseText = data.response || "No response generated.";
                                const aiMsg = document.createElement('div');
                                aiMsg.className = 'msg msg-ai';
                                aiMsg.innerHTML = applyStatusFormatting(marked.parse(responseText));
                                msgBox.appendChild(aiMsg);
                                vliChatSyncPointer++;
                                msgBox.scrollTop = msgBox.scrollHeight;
                            }
                        }
                        btn.classList.remove('processing');
                        btn.innerText = "➤";
                        isProcessing = false;
                        return;

                    } else {
                        // Standard Agent Directive
                        let rawDataMode = false;
                        if (rawText.toUpperCase().includes("--RAW") || (rawText.toUpperCase().includes("RAW") && (rawText.toUpperCase().includes("SMC") || rawText.toUpperCase().includes("DATA")))) {
                            rawDataMode = true;
                            requestText = rawText.replace(/--raw/ig, "").trim();
                        }

                        console.log("[VLI_TRACE] Forwarding command to backend: " + requestText);
                        const startTime = performance.now();
                        const res = await fetch('/api/vli/action-plan', {
                            method: 'POST',
                            headers: { 'Content-Type': 'application/json' },
                            body: JSON.stringify({
                                text: requestText,
                                direct_mode: directMode,
                                raw_data_mode: rawDataMode,
                                background_synthesis: asyncMode,
                                thread_id: lastVliThreadId,
                                snaptrade_settings: getSnaptradeSettings()
                            })
                        });
                        const data = await res.json();
                        if (data.thread_id) {
                            lastVliThreadId = data.thread_id;
                        }
                        const durationSec = ((performance.now() - startTime) / 1000).toFixed(2);
                        
                        if (isProcessing) {
                            if (isRegen) regenTargetAiMsg.innerHTML = "";
                            const responseText = data.response || "No response generated.";
                            
                            if (rawDataMode) {
                                const aiMsg = isRegen ? regenTargetAiMsg : document.createElement('div');
                                if (!isRegen) aiMsg.className = 'msg msg-ai';
                                try {
                                    const blob = new Blob([responseText], { type: 'application/json' });
                                    const url = URL.createObjectURL(blob);
                                    const artifactId = 'artifact_' + Date.now() + Math.floor(Math.random() * 1000);
                                    sessionArtifacts[artifactId] = responseText;
                                    aiMsg.innerHTML = `<div class="msg-ai-content"><strong>[HEADLESS DATA ENGINE - RAW JSON]:</strong><br>Returned <a href="${url}" download="vli_raw_payload.json" onclick="renderArtifactToReport(event, '${artifactId}')" style="color: #e5e7eb; font-weight: 700; text-decoration: underline; background: rgba(128, 128, 128, 0.25); padding: 4px 8px; border-radius: 4px; display: inline-block; margin-top: 10px; cursor: pointer;">vli_raw_payload.json</a><div style="font-size:10px; color:var(--text-muted); margin-top:8px;"> Latency: ${durationSec}s</div></div>`;
                                } catch (e) {
                                    aiMsg.innerHTML = `<div class="msg-ai-content"><strong>[HEADLESS DATA ENGINE - RAW JSON]:</strong> Data array returned successfully.<div style="font-size:10px; color:var(--text-muted); margin-top:8px;"> Latency: ${durationSec}s</div></div>`;
                                }
                                if (!isRegen) msgBox.appendChild(aiMsg);
                                vliChatSyncPointer++;
                            } else {
                                  // Process metadata directives for standard UI
                                  if (data.metadata && data.metadata.action === "OPEN_REPORT") {
                                      if (data.metadata.artifact_type === "REPORT") {
                                          window.openReportModal(data.metadata.symbol);
                                      }
                                      const aiMsg = document.createElement('div');
                                      aiMsg.className = 'msg msg-ai';
                                      aiMsg.style.borderColor = 'var(--emerald-green)';
                                      aiMsg.innerHTML = applyStatusFormatting(`**SYSTEM**: Opening ${data.metadata.artifact_type} UX Panel for **${data.metadata.symbol}**.`);
                                      msgBox.appendChild(aiMsg);
                                      vliChatSyncPointer++;
                                  } else if (data.metadata && data.metadata.action === "OPEN_CARD") {
                                      UXManager.createCard(data.metadata.card_type);
                                      const aiMsg = document.createElement('div');
                                      aiMsg.className = 'msg msg-ai';
                                      aiMsg.innerHTML = applyStatusFormatting(`**SYSTEM**: Spawned UX Module **${data.metadata.card_type}**.`);
                                      msgBox.appendChild(aiMsg);
                                      vliChatSyncPointer++;
                                  } else if (data.metadata && data.metadata.action === "CLOSE_CARD") {
                                      if (data.metadata.card_id === "ALL") {
                                          Object.keys(UXManager.instances).forEach(id => UXManager.removeCard(id));
                                          const aiMsg = document.createElement('div');
                                          aiMsg.className = 'msg msg-ai';
                                          aiMsg.style.borderColor = 'var(--ruby-red)';
                                          aiMsg.innerHTML = applyStatusFormatting(`**SYSTEM**: Terminated ALL UX Modules.`);
                                          msgBox.appendChild(aiMsg);
                                          vliChatSyncPointer++;
                                      } else {
                                          let found = false;
                                          Object.keys(UXManager.instances).forEach(id => {
                                              if (UXManager.instances[id].dataset.badge === data.metadata.card_id) {
                                                  UXManager.removeCard(id);
                                                  found = true;
                                              }
                                          });
                                          const aiMsg = document.createElement('div');
                                          aiMsg.className = 'msg msg-ai';
                                          if (found) {
                                              aiMsg.innerHTML = applyStatusFormatting(`**SYSTEM**: Terminated UX Module **${data.metadata.card_id}**.`);
                                          } else {
                                              aiMsg.style.borderColor = 'var(--ruby-red)';
                                              aiMsg.innerHTML = applyStatusFormatting(`**SYSTEM**: UX Module **${data.metadata.card_id}** not found or already closed.`);
                                          }
                                          msgBox.appendChild(aiMsg);
                                          vliChatSyncPointer++;
                                      }
                                  }
                            }
                            msgBox.scrollTop = msgBox.scrollHeight;
                        }
                    }
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
                    document.getElementById('profile-status').innerText = ' Backup created & Config saved successfully.';
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
    
        // 1d. Shield Results UI
        let activeShieldCandidates = [];
        window.vliNewShieldSymbols = new Set();
        
        function renderShieldResults(data) {
            if (!data.scanner_results || !data.scanner_results.candidates) return;
            
            // [HARDENING] Filter specifically for Core (SHIELD) tier
            const allCandidates = data.scanner_results.candidates;
            const shieldCandidates = allCandidates.filter(c => c.tier === 'SHIELD');

            // [NEW CANDIDATE TRACKING] Determine differential highlights
            const currentShieldSymbols = new Set(shieldCandidates.map(c => c.symbol));
            if (previousShieldSymbols.size > 0) {
                currentShieldSymbols.forEach(sym => {
                    if (!previousShieldSymbols.has(sym)) {
                        window.vliNewShieldSymbols.add(sym);
                    }
                });
            }
            previousShieldSymbols = currentShieldSymbols;

            const res = { ...data.scanner_results, candidates: shieldCandidates };
            
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
                            <div style="color: var(--emerald-green); font-weight: 800;">${(res.pulse_mode || '').includes('TradingView') ? 'Trading View - Shield Scan' : 'Defensive Shield'}</div>
                            <div style="font-family: var(--font-mono); font-size: 10px;">Updated: <span id="sh-updated-at" style="color: var(--emerald-green); font-weight: 800;">${new Date().toLocaleTimeString()}</span></div>
                        </div>
                        <table style="width:100%; border-collapse: collapse; font-family: 'Inter', sans-serif; font-size: 11px;">
                            <thead>
                                <tr style="border-bottom: 1px solid var(--card-border); color: var(--text-muted); font-size: 10px; text-transform: uppercase; letter-spacing: 0.5px;">
                                    <th style="padding: 8px 4px; text-align: left;">SYMBOL</th>
                                    <th style="padding: 8px 4px; text-align: right;">PRICE</th>
                                    <th style="padding: 8px 4px; text-align: right;">CHANGE</th>
                                    <th style="padding: 8px 4px; text-align: right;">SORTINO</th>
                                    <th style="padding: 8px 4px; text-align: center;">GRADE</th>
                                </tr>
                            </thead>
                            <tbody></tbody>
                        </table>
                    `;
                    table = body.querySelector('table');
                } else {
                    const timeEl = body.querySelector('#sh-updated-at');
                    if (timeEl) timeEl.innerText = new Date().toLocaleTimeString();
                }
                
                const tbody = table.querySelector('tbody');
                tbody.innerHTML = '';
                
                if (res.candidates.length === 0) {
                    tbody.innerHTML = `<tr style="border: none;"><td colspan="6" style="text-align: center; padding: 30px 10px; color: var(--text-muted); font-style: italic;">Scanner cache cleared. Standing by...</td></tr>`;
                }
                
                // ELITE GRADING LOGIC (Shield: Sortino Momentum vs Core)
                const validCandidates = res.candidates.filter(c => c.sortino !== undefined);
                if (validCandidates.length > 0) {
                    validCandidates.forEach(c => {
                        c.raw_power = c.sortino; // Promote using purely structural momentum
                    });
                    
                    const maxPower = Math.max(...validCandidates.map(c => c.raw_power));
                    const minPower = Math.min(...validCandidates.map(c => c.raw_power));
                    
                    res.candidates.forEach(c => {
                        if (c.raw_power === undefined) return;
                        
                        let percentile = 1.0;
                        if (maxPower > minPower) {
                            percentile = (c.raw_power - minPower) / (maxPower - minPower);
                        }
                        
                        c.heat_score = Math.floor(40 + (percentile * 60));
                        
                        if (c.heat_score >= 95) c.grade = 'S';
                        else if (c.heat_score >= 90) c.grade = 'A+';
                        else if (c.heat_score >= 82) c.grade = 'A';
                        else if (c.heat_score >= 75) c.grade = 'B+';
                        else if (c.heat_score >= 65) c.grade = 'B';
                        else if (c.heat_score >= 58) c.grade = 'C+';
                        else if (c.heat_score >= 50) c.grade = 'C';
                        else if (c.heat_score >= 35) c.grade = 'D';
                        else c.grade = 'F';
                    });
                }
                
                // Sort by elite heat_score
                res.candidates.sort((a, b) => (b.heat_score || 0) - (a.heat_score || 0));

                res.candidates.forEach(c => {
                    let gradeColor = 'var(--text-muted)';
                    let gradeBg = 'rgba(255,255,255,0.05)';
                    let gradeBorder = 'rgba(255,255,255,0.2)';

                    if (c.grade === 'S') { gradeColor = '#ffaa00'; gradeBg = 'rgba(255, 170, 0, 0.1)'; gradeBorder = 'rgba(255, 170, 0, 0.3)'; }
                    else if (c.grade === 'A+' || c.grade === 'A') { gradeColor = '#d866ff'; gradeBg = 'rgba(216, 102, 255, 0.1)'; gradeBorder = 'rgba(216, 102, 255, 0.3)'; }
                    else if (c.grade === 'B+' || c.grade === 'B') { gradeColor = '#00aaff'; gradeBg = 'rgba(0, 170, 255, 0.1)'; gradeBorder = 'rgba(0, 170, 255, 0.3)'; }
                    else if (c.grade === 'C+' || c.grade === 'C') { gradeColor = '#3fb950'; gradeBg = 'rgba(63, 185, 80, 0.1)'; gradeBorder = 'rgba(63, 185, 80, 0.3)'; }
                    else { gradeColor = 'var(--ruby-red)'; gradeBg = 'rgba(248, 81, 73, 0.1)'; gradeBorder = 'rgba(248, 81, 73, 0.3)'; }
                    
                    c.isNew = window.vliNewShieldSymbols.has(c.symbol);
                    const tr = document.createElement('tr');
                    tr.style.cursor = 'pointer';
                    tr.className = c.isNew ? 'scanner-res-row new-candidate-highlight' : 'scanner-res-row';
                    tr.style.transition = 'background 0.3s ease, opacity 0.5s ease, filter 0.5s ease';
                    
                    // [UX: TEMPORAL VERIFICATION]
                    const requestTime = window.vliRefreshingSymbols.get(c.symbol);
                    if (requestTime) {
                        const dataTime = c.updated_at ? new Date(c.updated_at).getTime() : 0;
                        if (dataTime > requestTime) {
                            console.log(`[VLI_UX] Shield Symbol ${c.symbol} refetched and verified fresh. Restoring formatting.`);
                            window.vliRefreshingSymbols.delete(c.symbol);
                        } else if (Date.now() - requestTime > 60000) {
                            console.log(`[VLI_UX] Shield Symbol ${c.symbol} refresh cancelled or interrupted.`);
                            window.vliRefreshingSymbols.delete(c.symbol);
                        }
                    }

                    const isRefreshing = window.vliRefreshingSymbols.has(c.symbol);
                    if (isRefreshing) {
                        tr.style.opacity = '1';
                        tr.style.filter = 'none';
                        tr.style.pointerEvents = 'none';
                    } else {
                        tr.style.opacity = '1';
                        tr.style.filter = 'none';
                        tr.style.pointerEvents = 'auto';
                    }
                    
                    tr.onmouseenter = () => {
                        if (window.vliNewShieldSymbols.has(c.symbol)) {
                            tr.classList.remove('new-candidate-highlight');
                            window.vliNewShieldSymbols.delete(c.symbol);
                            c.isNew = false;
                        }
                        tr.style.background = 'rgba(255,255,255,0.02)';
                    };
                    tr.onmouseleave = () => {
                        tr.style.background = 'transparent';
                    };
                    
                    // We keep the original onclick structure that existed in the core scanner
                    tr.onclick = () => { document.getElementById('cli-input').value = 'analyze ' + c.symbol; document.getElementById('rt-btn').click(); };
                    
                    const changeVal = parseFloat(c.change || c.gap || 0);
                    const changeColor = changeVal >= 0 ? 'var(--price-up)' : 'var(--price-down)';
                    
                    tr.innerHTML = `
                        <td style="padding: 10px 4px; color: #fff; font-weight: 700;">${c.symbol}</td>
                        <td style="padding: 10px 4px; text-align: right; font-family: var(--font-mono); color: #fff;">$${parseFloat(c.price || 0).toFixed(2)}</td>
                        <td style="padding: 10px 4px; text-align: right; font-family: var(--font-mono); color: ${changeColor};">${changeVal >= 0 ? '+' : ''}${changeVal.toFixed(2)}%</td>
                        <td style="padding: 10px 4px; text-align: right; font-family: var(--font-mono); color: ${(parseFloat(c.sortino || c.score || 0) < 0) ? 'var(--ruby-red)' : 'var(--emerald-green)'}; font-weight: 800;">${parseFloat(c.sortino || c.score || 0).toFixed(2)}</td>
                        <td style="padding: 10px 4px;">
                            <div style="display: flex; align-items: center; justify-content: flex-end;">
                                <span class="pulse-badge" style="display: inline-block; width: 32px; text-align: center; background: ${gradeBg}; color: ${gradeColor}; border: 1px solid ${gradeBorder}; font-size: 11px; padding: 2px 0;">${c.grade}</span>
                                <div style="width: 24px; display: flex; justify-content: flex-end;">
                                    ${isRefreshing ? 
                                    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="var(--amber-gold)" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" title="Retrieval in Progress"><circle cx="12" cy="14" r="8"></circle><polyline points="12 10 12 14 14 16"></polyline><line x1="10" y1="2" x2="14" y2="2"></line><line x1="12" y1="2" x2="12" y2="6"></line></svg>` 
                                    : 
                                    `<svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="color: ${c.has_report ? 'var(--emerald-green)' : 'rgba(255,255,255,0.2)'}; cursor: pointer;" onclick="event.stopPropagation(); window.openReportModal('${c.symbol}')" title="Structural Analysis"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>`}
                                </div>
                            </div>
                        </td>
                    `;
                    tbody.appendChild(tr);
                });
                
                const matchCountEl = document.getElementById('sh-match-count');
                if (matchCountEl) matchCountEl.innerText = res.candidates.length;
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
        
        // Auto-refresh pollers removed in favor of unified VLI poll cycle
        
        // --- SCHEDULER LOG LOGIC ---
        window.fetchSchedulerLogs = async function(instanceGuid) {
            const msgsContainer = document.getElementById(`scheduler-log-messages-${instanceGuid}`);
            if(!msgsContainer) return;
            
            try {
                const baseUrl = '';
                const res = await fetch(`${baseUrl}/api/scheduler/logs`);
                const data = await res.json();
                
                if(data.status === 'OK' && data.logs) {
                    const isAtBottom = msgsContainer.scrollHeight - msgsContainer.scrollTop <= msgsContainer.clientHeight + 20;
                    
                    let html = '';
                    data.logs.forEach(log => {
                        let color = 'var(--text-muted)';
                        if (log.includes('CRITICAL')) color = 'var(--text-alert)';
                        else if (log.includes('FAILED') || log.includes('MISFIRE')) color = 'var(--orange-warning)';
                        else if (log.includes('COMPLETED') || log.includes('EXECUTED')) color = 'var(--emerald-green)';
                        else if (log.includes('STARTED')) color = 'var(--cobalt-blue)';
                        html += `<div style="padding: 2px 10px; color: ${color};">${log}</div>`;
                    });
                    
                    if(html === '') {
                        html = '<div style="color: var(--text-muted); padding: 10px;">No rhythmic execution logs available.</div>';
                    }
                    
                    if (msgsContainer.innerHTML !== html) {
                        msgsContainer.innerHTML = html;
                        if (isAtBottom) {
                            msgsContainer.scrollTop = msgsContainer.scrollHeight;
                        }
                    }
                }
            } catch(e) {
                console.error("Scheduler fetch error", e);
            }
        };

        // --- End of Shield Logic ---
        
        // --- ORDER HISTORY LOGIC ---
        window.populateSnaptradeAccounts = async function(instanceGuid) {
            const selectEl = document.getElementById(`order-hist-account-${instanceGuid}`);
            if(!selectEl) return;
            try {
                const baseUrl = '';
                const res = await fetch(`${baseUrl}/api/brokerage/accounts`);
                const data = await res.json();
                if(data.accounts && data.accounts.length > 0) {
                    selectEl.innerHTML = '';
                    data.accounts.forEach(acc => {
                        const opt = document.createElement('option');
                        opt.value = acc.id;
                        opt.textContent = acc.name || acc.id;
                        if (acc.id.includes('Rollover IRA') || (acc.name && acc.name.includes('Rollover IRA'))) {
                            opt.selected = true;
                        }
                        selectEl.appendChild(opt);
                    });
                    
                    if (window.failedModules) window.failedModules.delete(`ACCOUNTS_${instanceGuid}`);
                    
                    // Fetch initial data after populating accounts if a date is set
                    const startVal = document.getElementById(`order-hist-start-${instanceGuid}`).value;
                    if(startVal) {
                        fetchOrderHistory(instanceGuid);
                    }
                } else {
                    selectEl.innerHTML = '<option value="">No Accounts Found</option>';
                }
            } catch (err) {
                console.error("Failed to populate SnapTrade accounts:", err);
                selectEl.innerHTML = '<option value="">Error Loading Accounts</option>';
                if (window.failedModules) window.failedModules.add(`ACCOUNTS_${instanceGuid}`);
            }
        };

        window.setOrderHistoryRange = function(rangeStr, instanceGuid, skipFetch = false) {
            const startEl = document.getElementById(`order-hist-start-${instanceGuid}`);
            const endEl = document.getElementById(`order-hist-end-${instanceGuid}`);
            if(!startEl || !endEl) return;
            if(rangeStr === 'custom') return;
            
            const end = new Date();
            let start = new Date();
            
            if(rangeStr === 'today') {
                // start is already today
            } else if (rangeStr === 'week') {
                start.setDate(end.getDate() - 7);
            } else if (rangeStr === 'month') {
                start.setMonth(end.getMonth() - 1);
            } else if (rangeStr === 'ytd') {
                start = new Date(end.getFullYear(), 0, 1);
            } else if (rangeStr === '1y') {
                start.setFullYear(end.getFullYear() - 1);
            }
            
            // Format to YYYY-MM-DD
            const getLocalIso = (d) => new Date(d.getTime() - d.getTimezoneOffset() * 60000).toISOString().split('T')[0];
            startEl.value = getLocalIso(start);
            endEl.value = getLocalIso(end);
            
            // Automatically fetch if account is already loaded
            if (!skipFetch) {
                const accountVal = document.getElementById(`order-hist-account-${instanceGuid}`).value;
                if(accountVal) {
                    fetchOrderHistory(instanceGuid);
                }
            }
        };
        
        window.validateOrderDateRange = function(type, instanceGuid) {
            const startInput = document.getElementById(`order-hist-start-${instanceGuid}`);
            const endInput = document.getElementById(`order-hist-end-${instanceGuid}`);
            
            if (startInput && endInput && startInput.value && endInput.value) {
                if (startInput.value > endInput.value) {
                    if (type === 'start') {
                        endInput.value = startInput.value;
                    } else if (type === 'end') {
                        startInput.value = endInput.value;
                    }
                }
            }
        };

        window.fetchOrderHistory = async function(instanceGuid, isBackground = false) {
            const rangeSelect = document.getElementById(`order-hist-range-${instanceGuid}`);
            if (rangeSelect && rangeSelect.value !== 'custom') {
                window.setOrderHistoryRange(rangeSelect.value, instanceGuid, true);
            }
            
            const accountId = document.getElementById(`order-hist-account-${instanceGuid}`).value;
            const startVal = document.getElementById(`order-hist-start-${instanceGuid}`).value;
            const endVal = document.getElementById(`order-hist-end-${instanceGuid}`).value;
            const symbolFilter = document.getElementById(`order-hist-symbol-${instanceGuid}`).value.toUpperCase().trim();
            const tbody = document.getElementById(`order-history-body-${instanceGuid}`);
            const pbody = document.getElementById(`positions-body-${instanceGuid}`);
            
            if(!accountId || !startVal || !endVal) {
                if (!isBackground) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-muted);">Please select account and date range.</td></tr>';
                    if (pbody) pbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px; color:var(--text-muted);">Please select account and date range.</td></tr>';
                }
                return;
            }
            
            if (!isBackground) {
                tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-muted);">Fetching...</td></tr>';
                if (pbody) pbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px; color:var(--text-muted);">Fetching...</td></tr>';
            }
            
            const filterBtn = document.getElementById(`order-hist-filter-btn-${instanceGuid}`);
            if (filterBtn && !isBackground) {
                filterBtn.disabled = true;
                filterBtn.style.opacity = '0.5';
                filterBtn.style.cursor = 'wait';
            }
            
            try {
                // Ensure we hit the Python backend directly
                const baseUrl = '';
                const url = `${baseUrl}/api/brokerage/history?account_id=${encodeURIComponent(accountId)}&start_date=${startVal}&end_date=${endVal}`;
                const res = await fetch(url);
                const data = await res.json();
                
                const cbody = document.getElementById(`closed-positions-body-${instanceGuid}`);
                
                if(data.error) {
                    tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--ruby-red);">Error: ${data.error}</td></tr>`;
                    if (pbody) pbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:20px; color:var(--ruby-red);">Error: ${data.error}</td></tr>`;
                    if (cbody) cbody.innerHTML = `<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--ruby-red);">Error: ${data.error}</td></tr>`;
                    return;
                }
                
                let history = data.history || [];
                let positions = data.positions || [];
                let closed = data.closed_positions || [];
                
                if(symbolFilter) {
                    history = history.filter(t => (t.symbol || '').toUpperCase() === symbolFilter);
                    positions = positions.filter(p => (p.symbol || '').toUpperCase() === symbolFilter);
                    closed = closed.filter(c => (c.symbol || '').toUpperCase() === symbolFilter);
                }
                
                if(history.length === 0) {
                    tbody.innerHTML = '<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--text-muted);">No trades found for this range.</td></tr>';
                } else {
                    let html = '';
                    history.forEach(t => {
                        const actionUpper = (t.action || 'N/A').toUpperCase();
                        const isBuy = actionUpper.includes('BUY');
                        const isSell = actionUpper.includes('SELL');
                        let actionHtml = actionUpper;
                        if(isBuy) actionHtml = `<span style="color:var(--emerald-green); font-weight:bold;">${actionUpper}</span>`;
                        else if (isSell) actionHtml = `<span style="color:var(--ruby-red); font-weight:bold;">${actionUpper}</span>`;
                        
                        html += `
                            <tr>
                                <td style="padding:4px; border-bottom:1px solid #333; color:var(--text-muted);">${t.time || ''}</td>
                                <td style="padding:4px; border-bottom:1px solid #333; font-weight:bold;">${t.symbol || ''}</td>
                                <td style="padding:4px; border-bottom:1px solid #333;">${actionHtml}</td>
                                <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">${t.qty || 0}</td>
                                <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">$${parseFloat(t.price || 0).toFixed(2)}</td>
                            </tr>
                        `;
                    });
                    tbody.innerHTML = html;
                }
                
                if (pbody) {
                    if (positions.length === 0) {
                        pbody.innerHTML = '<tr><td colspan="9" style="text-align:center; padding:20px; color:var(--text-muted);">No open positions found.</td></tr>';
                    } else {
                        let pHtml = '';
                        positions.forEach(p => {
                            const dGlPct = parseFloat(p.todays_gl_pct || 0);
                            const dGlDol = parseFloat(p.todays_gl_dol || 0);
                            const tGlPct = parseFloat(p.total_gl_pct || 0);
                            const tGlDol = parseFloat(p.total_gl_dol || 0);
                            
                            const dColor = dGlPct >= 0 ? 'var(--emerald-green)' : 'var(--ruby-red)';
                            const tColor = tGlPct >= 0 ? 'var(--emerald-green)' : 'var(--ruby-red)';
                            
                            pHtml += `
                                <tr>
                                    <td style="padding:4px; border-bottom:1px solid #333; color:var(--text-muted);">${p.last_time || ''}</td>
                                    <td style="padding:4px; border-bottom:1px solid #333; font-weight:bold;">${p.symbol || ''}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">$${parseFloat(p.last_price || 0).toFixed(2)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333; color:${dColor};">${dGlPct > 0 ? '+':''}${dGlPct.toFixed(2)}%</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333; color:${dColor};">${dGlDol > 0 ? '+$':'-$'}${Math.abs(dGlDol).toFixed(2)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333; color:${tColor};">${tGlPct > 0 ? '+':''}${tGlPct.toFixed(2)}%</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333; color:${tColor};">${tGlDol > 0 ? '+$':'-$'}${Math.abs(tGlDol).toFixed(2)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">${Math.ceil(p.qty || 0)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">$${parseFloat(p.average_cost || 0).toFixed(2)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">$${parseFloat(p.current_value || 0).toFixed(2)}</td>
                                </tr>
                            `;
                        });
                        pbody.innerHTML = pHtml;
                    }
                }
                
                if (cbody) {
                    if (closed.length === 0) {
                        cbody.innerHTML = '<tr><td colspan="7" style="text-align:center; padding:20px; color:var(--text-muted);">No closed positions found for this range.</td></tr>';
                    } else {
                        let cHtml = '';
                        
                        // Sort closed descending by date
                        closed.sort((a, b) => new Date(b.close_date || 0) - new Date(a.close_date || 0));
                        
                        closed.forEach(c => {
                            const pnlDol = parseFloat(c.pnl || 0);
                            const pnlPct = parseFloat(c.pnl_pct || 0);
                            const cColor = pnlDol >= 0 ? 'var(--emerald-green)' : 'var(--ruby-red)';
                            
                            // Format the ISO timestamp to a more readable format (YYYY-MM-DD HH:MM:SS)
                            let displayTime = c.close_date || '';
                            if (displayTime.includes('T')) {
                                displayTime = displayTime.replace('T', ' ').replace(/\.000Z$/, '').replace('Z', '');
                            }
                            
                            cHtml += `
                                <tr>
                                    <td style="padding:4px; border-bottom:1px solid #333; color:var(--text-muted);">${displayTime}</td>
                                    <td style="padding:4px; border-bottom:1px solid #333; font-weight:bold;">${c.symbol || ''}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">${Math.ceil(c.qty || 0)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">$${parseFloat(c.buy_price || 0).toFixed(2)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333;">$${parseFloat(c.sell_price || 0).toFixed(2)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333; color:${cColor};">${pnlDol > 0 ? '+$':'-$'}${Math.abs(pnlDol).toFixed(2)}</td>
                                    <td style="padding:4px; text-align:right; border-bottom:1px solid #333; color:${cColor};">${pnlPct > 0 ? '+':''}${pnlPct.toFixed(2)}%</td>
                                </tr>
                            `;
                        });
                        cbody.innerHTML = cHtml;
                    }
                }
                
                // --- UPDATE PNL SUMMARY ---
                let dayPnl = parseFloat(data.today_realized_pnl || 0);
                let unrealizedPnl = 0.0;
                let realizedPnl = parseFloat(data.realized_pnl_summary || 0);
                
                positions.forEach(p => {
                    unrealizedPnl += parseFloat(p.total_gl_dol || 0);
                });
                
                const totalPnl = unrealizedPnl + realizedPnl;
                
                const formatPnl = (val) => {
                    const color = val >= 0 ? 'var(--emerald-green)' : 'var(--ruby-red)';
                    const sign = val >= 0 ? '+' : '';
                    return `<span style="color:${color};">${sign}$${val.toFixed(2)}</span>`;
                };
                
                const elDay = document.getElementById(`pnl-day-${instanceGuid}`);
                const elUnr = document.getElementById(`pnl-unrealized-${instanceGuid}`);
                const elReal = document.getElementById(`pnl-realized-${instanceGuid}`);
                const elTot = document.getElementById(`pnl-total-${instanceGuid}`);
                
                if (elDay) elDay.innerHTML = formatPnl(dayPnl);
                if (elUnr) elUnr.innerHTML = formatPnl(unrealizedPnl);
                if (elReal) elReal.innerHTML = formatPnl(realizedPnl);
                if (elTot) elTot.innerHTML = formatPnl(totalPnl);
                
            } catch (err) {
                console.error("Failed to fetch order history:", err);
                tbody.innerHTML = `<tr><td colspan="5" style="text-align:center; padding:20px; color:var(--ruby-red);">Failed to fetch order history.</td></tr>`;
                if (pbody) pbody.innerHTML = `<tr><td colspan="9" style="text-align:center; padding:20px; color:var(--ruby-red);">Failed to fetch positions.</td></tr>`;
            } finally {
                if (filterBtn && !isBackground) {
                    filterBtn.disabled = false;
                    filterBtn.style.opacity = '1';
                    filterBtn.style.cursor = 'pointer';
                }
            }
        };
        // --- REPORT VIEWER LOGIC ---
        window.openReportModal = async function(symbol) {
            // Find a blank report viewer or spawn a new one via the UXManager
            let reportViewer = null;
            const viewers = document.querySelectorAll('.analysis-report-viewer-instance');
            for (const v of viewers) {
                if (v.innerText.includes("No report active.") || v.innerText.trim() === "") {
                    reportViewer = v;
                    break;
                }
            }
            if (!reportViewer) {
                const newCard = UXManager.createCard('STRUCTURAL_ANALY');
                if (newCard) {
                    reportViewer = newCard.querySelector('.analysis-report-viewer-instance');
                }
            }
            
            if (!reportViewer) return;
            
            const win = reportViewer.closest('.card');
            if (win) {
                const titleSpan = win.querySelector('.card-header > div:first-child > div:nth-child(2)');
                if (titleSpan) titleSpan.innerText = symbol.toUpperCase() + " Structural Analysis";
                bringToFront(win);
            }
            
            reportViewer.dataset.isStatic = "true";
            reportViewer.innerHTML = '<div style="text-align:center; padding: 40px; color: var(--text-muted);">Fetching Institutional Report...</div>';
            
            try {
                const res = await fetch(`/api/vli/report/${symbol}?t=${Date.now()}`);
                const data = await res.json();
                
                if(data.success) {
                    let formattedText = data.content;
                    let dynamicTitle = symbol.toUpperCase() + " Structural Analysis";
                    
                    let lines = formattedText.trim().split('\\n');
                    let headerLine = lines.find(line => /^#{1,4}\\s+/.test(line.trim()));
                    if (headerLine) {
                        dynamicTitle = headerLine.replace(/^#{1,4}\\s+/, '').replace(/[\\*\\_`]/g, '').trim();
                        if (dynamicTitle.length > 55) dynamicTitle = dynamicTitle.substring(0, 52) + "...";
                    }
                    
                    reportViewer.innerHTML = marked.parse(formattedText);
                    if (win) {
                        const titleSpan = win.querySelector('.card-header > div:first-child > div:nth-child(2)');
                        if (titleSpan) titleSpan.innerText = dynamicTitle;
                    }
                } else {
                    reportViewer.innerHTML = `<div style="color: var(--ruby-red); padding: 20px;">Report not yet generated for ${symbol}. Please wait for the background analyst or type <code>analyze ${symbol}</code> in the command center.</div>`;
                }
            } catch(e) {
                reportViewer.innerHTML = `<div style="color: var(--ruby-red); padding: 20px;">Error fetching report: ${e}</div>`;
            }
        };

        async function restartServer() {
            const btn = document.querySelector('button[title="Restart Server"]');
            if (btn) {
                btn.innerHTML = `<svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"><path d="M3 12a9 9 0 1 0 9-9 9.75 9.75 0 0 0-6.74 2.74L3 8"></path><path d="M3 3v5h5"></path></svg> Restarting...`;
                btn.style.opacity = '0.5';
                btn.style.pointerEvents = 'none';
            }
            
            const syncBadge = document.getElementById('menu-sync-status');
            const syncDot = document.getElementById('server-status-dot');
            const toggleBtn = document.getElementById('server-toggle-btn');
            if (syncBadge && toggleBtn && syncDot) {
                syncBadge.innerText = "Offline";
                toggleBtn.style.background = "rgba(225, 29, 72, 0.1)";
                toggleBtn.style.borderColor = "rgba(225, 29, 72, 0.3)";
                toggleBtn.style.color = "var(--ruby-red)";
                syncDot.style.backgroundColor = "var(--ruby-red)";
            }
            
            try {
                // Wait for the server to acknowledge the restart command
                await fetch('/api/system/restart', { method: 'POST' });
            } catch(e) {
                console.log("Expected restart drop:", e);
            }
            
            // The server acknowledged the restart, so it is now starting its 1s shutdown delay + 2s wrapper delay.
            // Let's wait 2.5s so we are guaranteed to start the reconnecting workflow exactly when the server is dead.
            setTimeout(() => {
                window.vliStartHandshake(true);
            }, 2500);
        }

        let vliPollingEnabled = true;
        function toggleServerConnection() {
            vliPollingEnabled = !vliPollingEnabled;
            const syncBadge = document.getElementById('menu-sync-status');
            const syncDot = document.getElementById('server-status-dot');
            const toggleBtn = document.getElementById('server-toggle-btn');
            
            if (vliPollingEnabled) {
                syncBadge.innerText = "Connecting...";
                toggleBtn.style.opacity = "0.7";
                window.vliStartHandshake();
            } else {
                syncBadge.innerText = "Offline";
                toggleBtn.style.background = "rgba(225, 29, 72, 0.1)";
                toggleBtn.style.borderColor = "rgba(225, 29, 72, 0.3)";
                toggleBtn.style.color = "var(--ruby-red)";
                syncDot.style.backgroundColor = "var(--ruby-red)";
                toggleBtn.style.opacity = "1";
            }
        }
    