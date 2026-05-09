
        document.addEventListener("DOMContentLoaded", () => {
            const inputElement = document.getElementById('chat-input');
            if (inputElement && typeof handleChatInputKeyDown === 'function') {
                inputElement.addEventListener('keydown', handleChatInputKeyDown);
            }
            // Initialize with Coordinator active in the integrated panel
            switchSidebarTab('coordinator');

            // [NEW] Proactively suppress floating coordinator card to favor integrated sidebar
            setTimeout(() => {
                if (typeof UXManager !== 'undefined') {
                    console.log("[VLI_SYSTEM] Suppressing floating coordinator card on startup...");
                    UXManager.closeCard('CI');
                }
            }, 1500);
        });

        window.vliTabWidths = { coordinator: 380, artifacts: 380, strategy: 450 };
        let activeSidebarTabs = new Set();
        
        // --- SIDEBAR RESIZING LOGIC ---
        document.addEventListener('DOMContentLoaded', () => {
            const resizers = document.querySelectorAll('.sidebar-resizer');
            
            let isResizingSidebar = false;
            let startX;
            let startWidths = {};
            let activeResizerId = null;
            
            resizers.forEach(resizer => {
                resizer.addEventListener('mousedown', (e) => {
                    isResizingSidebar = true;
                    activeResizerId = resizer.getAttribute('data-tab-id');
                    startX = e.clientX;
                    
                    Object.keys(window.vliTabWidths).forEach(k => {
                        startWidths[k] = window.vliTabWidths[k];
                    });
                    
                    resizer.classList.add('active');
                    document.body.style.cursor = 'ew-resize';
                    document.body.style.userSelect = 'none';
                });
            });
            
            document.addEventListener('mousemove', (e) => {
                if (!isResizingSidebar || !activeResizerId) return;
                
                const numActive = activeSidebarTabs.size;
                if (numActive === 0) return;
                
                const dx = startX - e.clientX; 
                let newWidth;
                if (activeResizerId === 'coordinator') {
                    newWidth = startWidths[activeResizerId] + dx;
                } else if (activeResizerId === 'artifacts' || activeResizerId === 'strategy') {
                    newWidth = startWidths[activeResizerId] - dx;
                }
                
                newWidth = Math.max(250, newWidth);
                const maxAllowedTotalWidth = window.innerWidth / 2;
                if (newWidth > maxAllowedTotalWidth) newWidth = maxAllowedTotalWidth;
                
                window.vliTabWidths[activeResizerId] = newWidth;
                
                if (activeResizerId === 'coordinator') {
                    const rightSidebar = document.getElementById('vli-sidebar-right');
                    const rightTabs = document.getElementById('sidebar-tabs-right');
                    const watermark = document.getElementById('vli-version-watermark');
                    rightSidebar.style.width = `${newWidth}px`;
                    rightTabs.style.right = `${newWidth}px`;
                    if (watermark) watermark.style.right = `${newWidth + 20}px`;
                } else if (activeResizerId === 'artifacts' || activeResizerId === 'strategy') {
                    const leftSidebar = document.getElementById('vli-sidebar-left');
                    const leftTabs = document.getElementById('sidebar-tabs-left');
                    leftSidebar.style.width = `${newWidth}px`;
                    leftTabs.style.left = `${newWidth}px`;
                }
            });
            
            document.addEventListener('mouseup', () => {
                if (isResizingSidebar) {
                    isResizingSidebar = false;
                    resizers.forEach(r => r.classList.remove('active'));
                    document.body.style.cursor = 'default';
                    document.body.style.userSelect = 'auto';
                }
            });
        });

        function switchSidebarTab(tabId) {
            console.log("[VLI_SIDEBAR] Toggling tab:", tabId);
            
            const isLeftTab = tabId === 'artifacts' || tabId === 'strategy';
            
            if (activeSidebarTabs.has(tabId)) {
                activeSidebarTabs.delete(tabId);
            } else {
                if (isLeftTab) {
                    activeSidebarTabs.delete('artifacts');
                    activeSidebarTabs.delete('strategy');
                }
                activeSidebarTabs.add(tabId);
                
                if (tabId === 'coordinator' && typeof UXManager !== 'undefined') {
                    const activeCards = document.querySelectorAll('.card');
                    activeCards.forEach(card => {
                        if (card.id && card.id.startsWith('win-CI')) {
                            console.log("[VLI_SYSTEM] Suppressing floating coordinator card...");
                            UXManager.closeCard('CI');
                        }
                    });
                }
            }
            
            // Sync UI states
            document.querySelectorAll('.folder-tab').forEach(el => {
                const id = el.id.replace('tab-btn-', '');
                if (activeSidebarTabs.has(id)) el.classList.add('active');
                else el.classList.remove('active');
            });
            
            // Handle Artifacts/Strategy (Left)
            const leftSidebar = document.getElementById('vli-sidebar-left');
            const leftTabs = document.getElementById('sidebar-tabs-left');
            
            document.getElementById('tab-artifacts').style.display = activeSidebarTabs.has('artifacts') ? 'block' : 'none';
            document.getElementById('tab-strategy').style.display = activeSidebarTabs.has('strategy') ? 'flex' : 'none';
            
            if (activeSidebarTabs.has('artifacts') || activeSidebarTabs.has('strategy')) {
                const activeId = activeSidebarTabs.has('artifacts') ? 'artifacts' : 'strategy';
                leftSidebar.style.transform = 'translateX(0)';
                leftSidebar.style.width = window.vliTabWidths[activeId] + 'px';
                leftTabs.style.left = window.vliTabWidths[activeId] + 'px';
                if (activeId === 'artifacts') loadArtifactTree();
                if (activeId === 'strategy') initStrategySidebar();
            } else {
                leftSidebar.style.transform = 'translateX(-100%)';
                leftSidebar.style.width = '0px';
                leftTabs.style.left = '0px';
            }
            
            // Handle Coordinator (Right)
            const rightSidebar = document.getElementById('vli-sidebar-right');
            const rightTabs = document.getElementById('sidebar-tabs-right');
            const watermark = document.getElementById('vli-version-watermark');
            if (activeSidebarTabs.has('coordinator')) {
                rightSidebar.style.transform = 'translateX(0)';
                rightSidebar.style.width = window.vliTabWidths['coordinator'] + 'px';
                rightTabs.style.right = window.vliTabWidths['coordinator'] + 'px';
                if (watermark) watermark.style.right = (window.vliTabWidths['coordinator'] + 20) + 'px';
                const input = document.getElementById('chat-input');
                if (input) setTimeout(() => input.focus(), 100);
            } else {
                rightSidebar.style.transform = 'translateX(100%)';
                rightSidebar.style.width = '0px';
                rightTabs.style.right = '0px';
                if (watermark) watermark.style.right = '16px';
            }
        }
        
        async function loadArtifactTree() {
            try {
                // Snapshot currently open folders to prevent collapse on redraw
                const openFolders = new Set();
                document.querySelectorAll('.tree-folder.open > .tree-item > div > .tree-label').forEach(el => {
                    openFolders.add(el.textContent.trim());
                });

                const res = await fetch('/api/vli/artifacts/tree');
                const data = await res.json();
                const container = document.getElementById('artifact-tree-container');
                container.innerHTML = '';
                
                if (data.tree) {
                    data.tree.forEach(node => {
                        container.appendChild(createTreeNode(node, openFolders));
                    });
                }
            } catch (e) {
                console.error('Failed to load artifact tree', e);
            }
        }
        
        function createTreeNode(node, openFolders = new Set()) {
            const wrapper = document.createElement('div');
            
            if (node.type === 'folder') {
                wrapper.className = 'tree-folder';
                wrapper.dataset.path = node.path || node.name;
                
                const d = new Date();
                const todayStr = `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
                const isToday = node.name === todayStr;
                
                if (openFolders.has(node.name) || window.vliForceOpenFolder === node.name || isToday) {
                    wrapper.classList.add('open');
                }
                
                const item = document.createElement('div');
                item.className = 'tree-item';
                
                const bgColor = isToday ? 'rgba(236, 72, 153, 0.15)' : 'transparent';
                const textColor = isToday ? '#ec4899' : 'var(--text-muted)';
                item.style.backgroundColor = bgColor;
                if (isToday) item.style.borderRadius = '4px';
                
                let extraBtns = '';
                if (node.name === 'Notes') {
                    extraBtns = `<div class="tree-add-btn" title="Add New Note" style="margin-left: auto; cursor: pointer; opacity: 0.6; font-size: 12px; padding-right: 8px;"></div>`;
                }
                item.innerHTML = `<div style="display:flex; flex:1; align-items:center; width:100%;"><div class="tree-icon"></div><div class="tree-label" style="font-weight:700; color:${textColor};">${node.name}</div>${extraBtns}</div>`;
                item.onclick = (e) => {
                    if (e.target.closest('.tree-add-btn')) {
                        e.stopPropagation();
                        fetch('/api/vli/artifacts/create', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ folder: node.path || node.name })
                        }).then(res => res.json())
                          .then(data => { 
                              if (data.status === 'OK') {
                                  loadArtifactTree(); 
                                  if (data.path) {
                                      fetch('/api/vli/artifacts/open_local', {
                                          method: 'POST',
                                          headers: {'Content-Type': 'application/json'},
                                          body: JSON.stringify({ path: data.path })
                                      }).catch(e => console.error('Error auto-opening file:', e));
                                  }
                              } 
                          })
                          .catch(err => console.error(err));
                        return;
                    }
                    wrapper.classList.toggle('open');
                };
                
                const childrenContainer = document.createElement('div');
                childrenContainer.className = 'tree-children';
                node.children.forEach(child => {
                    childrenContainer.appendChild(createTreeNode(child, openFolders));
                });
                
                wrapper.appendChild(item);
                wrapper.appendChild(childrenContainer);
            } else {
                wrapper.className = 'tree-file';
                
                const item = document.createElement('div');
                item.className = 'tree-item';
                
                let displayName = node.name;
                if (displayName.endsWith('.md')) {
                    displayName = displayName.substring(0, displayName.length - 3);
                }
                
                let buttonsHtml = '<div style="display:flex; margin-left: auto;">';
                if (node.canRename) {
                    buttonsHtml += `<div class="tree-rename-btn" title="Rename Report" style="cursor: pointer; opacity: 0.6; font-size: 12px; padding-right: 8px;"></div>`;
                }
                buttonsHtml += `<div class="tree-local-btn" title="Edit File Locally" style="cursor: pointer; opacity: 0.6; font-size: 12px; padding-right: 8px;"></div>`;
                if (node.canDelete) {
                    buttonsHtml += `<div class="tree-delete-btn" title="Delete Report" style="cursor: pointer; opacity: 0.6; font-size: 12px; padding-right: 8px; color: #f85149;"></div>`;
                }
                buttonsHtml += '</div>';

                item.innerHTML = `<div class="tree-icon" style="opacity:0.3;">≡</div><div class="tree-label" style="display:flex; width:100%; align-items:center;"><span>${displayName}</span>${buttonsHtml}</div>`;
                
                item.onclick = (e) => {
                    if (e.target.closest('.tree-delete-btn')) {
                        e.stopPropagation();
                        fetch('/api/vli/artifacts/delete', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ path: node.path })
                        }).then(res => res.json())
                          .then(data => {
                              if (data.status === 'OK') loadArtifactTree();
                              else alert('Delete failed: ' + (data.detail || data.message));
                          })
                          .catch(err => alert('Error deleting file: ' + err));
                        return;
                    }
                    if (e.target.closest('.tree-rename-btn')) {
                        e.stopPropagation();
                        const labelContainer = item.querySelector('.tree-label');
                        const labelSpan = labelContainer.querySelector('span');
                        
                        if (labelContainer.querySelector('input')) return;
                        
                        const currentName = labelSpan.textContent;
                        const input = document.createElement('input');
                        input.type = 'text';
                        input.value = currentName.replace('.md', '');
                        input.style.flex = '1';
                        input.style.background = '#0d1117';
                        input.style.color = '#c9d1d9';
                        input.style.border = '1px solid #30363d';
                        input.style.borderRadius = '4px';
                        input.style.padding = '2px 6px';
                        input.style.fontSize = '12px';
                        input.style.marginRight = '8px';
                        
                        labelSpan.style.display = 'none';
                        labelContainer.insertBefore(input, labelSpan);
                        input.focus();
                        input.select();
                        
                        let isRenaming = false;
                        const handleRename = () => {
                            if (isRenaming) return;
                            isRenaming = true;
                            
                            let newName = input.value.trim();
                            if (newName && newName !== currentName.replace('.md', '')) {
                                fetch('/api/vli/artifacts/rename', {
                                    method: 'POST',
                                    headers: {'Content-Type': 'application/json'},
                                    body: JSON.stringify({ old_path: node.path, new_name: newName })
                                }).then(res => res.json())
                                  .then(data => {
                                      if (data.status === 'OK') loadArtifactTree();
                                      else {
                                          alert('Rename failed: ' + (data.detail || data.message));
                                          input.remove();
                                          labelSpan.style.display = '';
                                      }
                                  })
                                  .catch(err => {
                                      alert('Error renaming file: ' + err);
                                      input.remove();
                                      labelSpan.style.display = '';
                                  });
                            } else {
                                input.remove();
                                labelSpan.style.display = '';
                            }
                        };
                        
                        input.addEventListener('blur', handleRename);
                        input.addEventListener('keydown', (evt) => {
                            if (evt.key === 'Enter') handleRename();
                            if (evt.key === 'Escape') {
                                isRenaming = true;
                                input.remove();
                                labelSpan.style.display = '';
                            }
                        });
                        return;
                    }

                    if (e.target.closest('.tree-local-btn')) {
                        e.stopPropagation();
                        fetch('/api/vli/artifacts/open_local', {
                            method: 'POST',
                            headers: {'Content-Type': 'application/json'},
                            body: JSON.stringify({ path: node.path })
                        }).then(res => res.json())
                          .catch(err => console.error('Error opening local file:', err));
                        return;
                    }

                    openArtifact(node.path, node.name);
                };
                wrapper.appendChild(item);
            }
            
            return wrapper;
        }
        
        async function openArtifact(path, name) {
            try {
                const res = await fetch('/api/vli/artifacts/content?path=' + encodeURIComponent(path));
                const data = await res.json();
                if (data.content) {
                    if (typeof CARD_TYPES !== 'undefined' && !CARD_TYPES['ARTIFACT_VIEWER']) {
                        CARD_TYPES['ARTIFACT_VIEWER'] = {
                            idPrefix: "ART",
                            title: "Artifact Viewer",
                            isSingleton: false,
                            initContent: () => `<div class="artifact-content msg-ai" style="padding:15px; overflow-y:auto; height:100%;"></div>`,
                            onAttach: () => {}
                        };
                    }
                    
                    const card = UXManager.createCard('ARTIFACT_VIEWER', {
                        top: '100px',
                        left: '100px',
                        width: '700px',
                        height: '600px'
                    });
                    
                    if (card) {
                        card.dataset.artifactPath = path;
                        const titleEl = card.querySelector('.card-header > div:first-child > div:nth-child(2)');
                        if (titleEl) titleEl.innerText = name;
                        const contentEl = card.querySelector('.artifact-content');
                        if (contentEl) {
                            contentEl.innerHTML = marked.parse(data.content);
                            contentEl.style.color = "var(--text-muted)";
                        }
                    }
                }
            } catch(e) {
                console.error('Failed to load artifact content', e);
            }
        }

        let activeStrategySubTab = 'strategy';
        let sidebarProfileState = null;
        
        async function initStrategySidebar() {
            try {
                const res = await fetch('/api/v1/trader-profile');
                if (res.ok) {
                    sidebarProfileState = await res.json();
                    switchStrategySubTab(activeStrategySubTab);
                }
            } catch(e) {
                console.error('Failed to init strategy sidebar', e);
            }
        }
        
        function switchStrategySubTab(tabName) {
            activeStrategySubTab = tabName;
            
            document.querySelectorAll('#tab-strategy .modal-tab').forEach(el => el.classList.remove('active'));
            document.getElementById('sidebar-tab-btn-' + tabName).classList.add('active');
            
            const selector = document.getElementById('sidebar-module-selector');
            selector.innerHTML = '';
            
            let files = [];
            let activeFile = '';
            let activeContent = '';
            
            if (tabName === 'persona') {
                files = sidebarProfileState.persona_files;
                activeFile = sidebarProfileState.active_persona;
                activeContent = sidebarProfileState.persona;
            } else if (tabName === 'strategy') {
                files = sidebarProfileState.strategy_files;
                activeFile = sidebarProfileState.active_strategy;
                activeContent = sidebarProfileState.strategy;
            } else if (tabName === 'rules') {
                files = sidebarProfileState.rules_files;
                activeFile = sidebarProfileState.active_rules;
                activeContent = sidebarProfileState.rules;
            }
            
            files.forEach(f => {
                const opt = document.createElement('option');
                opt.value = f;
                opt.textContent = f;
                selector.appendChild(opt);
            });
            selector.value = activeFile;
            
            renderSidebarModuleContent(activeContent);
        }
        
        function renderSidebarModuleContent(content) {
            const summaryBlock = document.getElementById('sidebar-module-summary');
            const contentBlock = document.getElementById('sidebar-module-content');
            
            if (!content) {
                summaryBlock.style.display = 'none';
                contentBlock.innerHTML = 'No content available.';
                return;
            }
            
            // Extract the first paragraph after the title
            const lines = content.split('\n');
            let summaryText = '';
            let contentStartIndex = 0;
            
            for (let i = 0; i < lines.length; i++) {
                const line = lines[i].trim();
                if (line.startsWith('# ')) {
                    // skip title
                    continue;
                }
                if (line && !line.startsWith('#')) {
                    // This is our first paragraph
                    summaryText = line;
                    contentStartIndex = i + 1;
                    // if next lines are also text, keep appending until blank line or header
                    for (let j = i + 1; j < lines.length; j++) {
                        const nextLine = lines[j].trim();
                        if (!nextLine || nextLine.startsWith('#')) {
                            contentStartIndex = j;
                            break;
                        }
                        summaryText += ' ' + nextLine;
                    }
                    break;
                }
            }
            
            if (summaryText) {
                summaryBlock.style.display = 'block';
                summaryBlock.innerHTML = `<strong>SUMMARY:</strong> ${summaryText}`;
            } else {
                summaryBlock.style.display = 'none';
            }
            
            // The rest of the content
            const remainingContent = lines.slice(contentStartIndex).join('\n');
            contentBlock.innerHTML = marked.parse(remainingContent || content);
        }
        
        async function onSidebarModuleChange() {
            const selector = document.getElementById('sidebar-module-selector');
            const targetFile = selector.value;
            
            document.getElementById('sidebar-module-content').innerHTML = 'Loading module...';
            
            try {
                // Update active file in the backend
                const payload = {};
                if (activeStrategySubTab === 'persona') {
                    payload.active_persona = targetFile;
                    sidebarProfileState.active_persona = targetFile;
                } else if (activeStrategySubTab === 'strategy') {
                    payload.active_strategy = targetFile;
                    sidebarProfileState.active_strategy = targetFile;
                } else if (activeStrategySubTab === 'rules') {
                    payload.active_rules = targetFile;
                    sidebarProfileState.active_rules = targetFile;
                }
                
                await fetch('/api/v1/trader-profile/active-modules', {
                    method: 'POST',
                    headers: {'Content-Type': 'application/json'},
                    body: JSON.stringify(payload)
                });
                
                // Fetch the new file content
                const res = await fetch('/api/v1/trader-profile/file?name=' + encodeURIComponent(targetFile));
                if (res.ok) {
                    const data = await res.json();
                    
                    if (activeStrategySubTab === 'persona') sidebarProfileState.persona = data.content;
                    else if (activeStrategySubTab === 'strategy') sidebarProfileState.strategy = data.content;
                    else if (activeStrategySubTab === 'rules') sidebarProfileState.rules = data.content;
                    
                    renderSidebarModuleContent(data.content);
                }
            } catch(e) {
                console.error('Failed to change sidebar module', e);
                document.getElementById('sidebar-module-content').innerHTML = 'Error loading module.';
            }
        }
        // Initialize on load
        window.addEventListener('DOMContentLoaded', () => {
            initScannerSettings();
            
            // Wait a brief moment to ensure UI frames are ready before fetching scanner
            setTimeout(() => {
                initScannerSSE();
            }, 500);
        });
    