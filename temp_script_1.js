
        if ('serviceWorker' in navigator) {
            window.addEventListener('load', () => {
                navigator.serviceWorker.register('/sw.js').catch(err => console.log('SW registration failed: ', err));
            });
        }
        window.failedModules = new Set();
        let handshakeSeconds = 0;
        let handshakeInterval = null;
        let handshakeRestartAttempted = false;
        
        let hasTimedOutOnce = false;
        
        window.showServerOffline = function(message = 'SERVER RESTARTING', details = '') {
            if (message === 'SERVER OFFLINE') hasTimedOutOnce = true;
            // Removed clearInterval to allow continuous polling in background
            
            document.getElementById('vli-handshake-overlay').style.display = 'flex';
            document.getElementById('vli-handshake-dialog').style.background = '#0d111b';
            
            if (details) {
                document.getElementById('vli-handshake-details').style.display = 'block';
                document.getElementById('vli-handshake-details').innerHTML = details;
            } else {
                document.getElementById('vli-handshake-details').style.display = 'none';
            }
            
            document.getElementById('vli-handshake-title').innerText = message;
            document.getElementById('vli-handshake-title').style.color = '#ffffff';
            
            const bar = document.getElementById('vli-handshake-bar');
            bar.style.animation = 'none';
            bar.style.transform = 'translateX(0)';
            bar.style.width = '100%';
            bar.style.background = 'var(--ruby-red)';
            bar.style.boxShadow = '0 0 15px rgba(248, 81, 73, 0.4)';
            
            setTimeout(() => {
                document.getElementById('vli-handshake-bar-container').style.display = 'none';
                
                document.getElementById('vli-handshake-actions').style.display = 'flex';
                document.getElementById('vli-handshake-retry').style.background = '#21262d';
                document.getElementById('vli-handshake-retry').style.color = '#e6edf3';
            }, 500);
        }

        window.vliStartHandshake = function(isRestarting = false) {
            // Auto-launch the backend via the Next.js orchestrator immediately when the client starts
            if (window.location.hostname === 'localhost' || window.location.hostname === '127.0.0.1' || window.location.hostname === '') {
                originalFetch('http://127.0.0.1:3000/api/system/startup', { method: 'POST' }).catch(e => console.error("[VLI_LAUNCHER] Orchestrator unreachable:", e));
                hasTimedOutOnce = false;
            }

            window._vliHandshakeIsRestarting = isRestarting;
            let baseText = isRestarting ? "Launching Server" : "Connecting to Server";

            document.getElementById('vli-handshake-overlay').style.display = 'flex';
            document.getElementById('vli-handshake-dialog').style.background = '#0d111b';
            document.getElementById('vli-handshake-title').innerText = `${baseText} (0s)`;
            document.getElementById('vli-handshake-title').style.color = 'var(--text-muted)';
            document.getElementById('vli-handshake-actions').style.display = 'none';
            document.getElementById('vli-handshake-bar-container').style.display = 'block';
            
            const bar = document.getElementById('vli-handshake-bar');
            bar.style.width = '70%';
            bar.style.background = 'linear-gradient(90deg, transparent 0%, var(--cobalt-blue) 50%, transparent 100%)';
            bar.style.boxShadow = '0 0 15px rgba(88, 166, 255, 0.4)';
            bar.style.animation = 'sweep 1.2s ease-in-out infinite';
            bar.style.transform = 'translateX(-100%)';
            
            handshakeSeconds = 0;
            isHandshakeFetching = false;
            
            if (handshakeInterval) clearInterval(handshakeInterval);
            
            handshakeInterval = setInterval(async () => {
                handshakeSeconds++;
                
                if (handshakeSeconds >= 60) {
                    window.showServerOffline('RECONNECTING', 'Server launch timed out. Running refresh script...');
                    setTimeout(() => window.location.reload(true), 2000);
                    return;
                }
                
                let baseText = window._vliHandshakeIsRestarting ? "Launching Server" : "Connecting to Server";
                document.getElementById('vli-handshake-title').innerText = `${baseText} (${handshakeSeconds}s)`;
                
                if (isHandshakeFetching) return;
                isHandshakeFetching = true;
                
                try {
                    const res = await originalFetch(`/api/health?_t=${Date.now()}`, { cache: 'no-store' });
                    if (res.ok) {
                        const data = await res.json();
                        if (data.version === VLI_CLIENT_VERSION) {
                            clearInterval(handshakeInterval);
                            handshakeSeconds = 0;
                            
                            const finishConnection = () => {
                                document.getElementById('vli-handshake-title').innerText = 'Connected!';
                                document.getElementById('vli-handshake-title').style.color = 'var(--emerald-green)';
                                bar.style.animation = 'none';
                                bar.style.transform = 'translateX(0)';
                                bar.style.width = '100%';
                                bar.style.background = 'var(--emerald-green)';
                                bar.style.boxShadow = '0 0 15px rgba(63, 185, 80, 0.4)';
                            };
                            
                            if (window._vliHandshakeIsRestarting) {
                                document.getElementById('vli-handshake-title').innerText = 'Connecting to Server...';
                                setTimeout(finishConnection, 800);
                            } else {
                                finishConnection();
                            }
                            
                            // Self-healing: Re-trigger failed modules
                            if (window.UXManager && window.UXManager.instances) {
                                Object.values(window.UXManager.instances).forEach(card => {
                                    if (card.dataset && card.dataset.typeGuid === 'ORDER_HIST') {
                                        const guid = card.id.replace('win-', '');
                                        if (window.populateSnaptradeAccounts) {
                                            console.log(`[VLI_HEAL] Refreshing SnapTrade accounts for ORDER_HIST module ${guid}`);
                                            window.populateSnaptradeAccounts(guid);
                                        }
                                    }
                                });
                            }
                            if (window.failedModules && window.failedModules.size > 0) {
                                console.log("[VLI_HEAL] Detected reconnection. Healing generic modules:", window.failedModules);
                                window.failedModules.forEach(mod => {
                                    // other modules handled here
                                });
                            }
                            
                            setTimeout(() => {
                                document.getElementById('vli-handshake-overlay').style.display = 'none';
                            }, 1000);
                        } else {
                            if (!window.hasTriggeredVersionRestart) {
                                window.hasTriggeredVersionRestart = true;
                                window.showServerOffline('RESTARTING', 'Version mismatch detected. Booting updated backend instance...');
                                try {
                                    await originalFetch('/api/system/restart', { method: 'POST' });
                                } catch (err) {}
                            }
                        }
                    } else {
                        if (handshakeSeconds >= 60) {
                            window.showServerOffline('RECONNECTING', 'Server launch timed out. Running refresh script...');
                            setTimeout(() => window.location.reload(true), 2000);
                            return;
                        }
                    }
                } catch (err) {
                    if (handshakeSeconds >= 60) {
                        window.showServerOffline('RECONNECTING', 'Server launch timed out. Running refresh script...');
                        setTimeout(() => window.location.reload(true), 2000);
                        return;
                    }
                } finally {
                    isHandshakeFetching = false;
                }
            }, 1000);
        };
        
        async function runOfflineCheck() {
            try {
                const res = await originalFetch(`/api/health?_t=${Date.now()}`, { cache: 'no-store' });
                if (!res.ok) {
                    window.vliStartHandshake(true);
                    return;
                }
                const data = await res.json();
                if (!data || !data.version) {
                    window.vliStartHandshake(true);
                }
            } catch(e) {
                window.vliStartHandshake(true);
            }
        }

        if (document.readyState === 'loading') {
            window.addEventListener('DOMContentLoaded', runOfflineCheck);
        } else {
            runOfflineCheck();
        }
    