// content.js
// Runs in the ISOLATED world and extracts the hydrated DOM

console.log("[VLI Bridge] Content script active. Waiting for Angular to hydrate...");

// Deep DOM text extractor that pierces Shadow DOMs
function extractDeepText(node) {
    let text = '';
    
    // If it's a text node, return its content
    if (node.nodeType === Node.TEXT_NODE) {
        return node.nodeValue + ' ';
    }
    
    // Check for Shadow DOM
    if (node.shadowRoot) {
        text += extractDeepText(node.shadowRoot);
    }
    
    // Traverse standard children
    if (node.childNodes) {
        node.childNodes.forEach(child => {
            text += extractDeepText(child);
        });
    }
    return text;
}

console.log("[VLI Bridge] Content script active. Polling for Angular to hydrate...");

let attempts = 0;
const poll = setInterval(() => {
    attempts++;
    console.log(`[VLI Bridge] Polling for order details... (Attempt ${attempts})`);
    
    // Find all explicitly designated row-expand icons
    const buttons = document.querySelectorAll('div.expandCollapseIcon');
    let clicked = 0;
    buttons.forEach(btn => {
        // Only click if it's not already expanded
        if (btn.getAttribute('aria-expanded') !== 'true') {
            if (!btn.dataset.vliDiscovered) {
                btn.dataset.vliDiscovered = Date.now().toString();
                return; // Let Angular fully hydrate new rows
            }
            if (Date.now() - parseInt(btn.dataset.vliDiscovered) < 3000) {
                return; // Wait 3 seconds before first interaction
            }
            
            try { 
                const rect = btn.getBoundingClientRect();
                const x = rect.left + (rect.width / 2);
                const y = rect.top + (rect.height / 2);
                const opts = { bubbles: true, cancelable: true, view: window, clientX: x, clientY: y };
                
                // Full accessibility interaction simulation for custom Angular elements
                btn.focus();
                btn.dispatchEvent(new MouseEvent('mousedown', opts));
                btn.dispatchEvent(new MouseEvent('mouseup', opts));
                btn.click();
                btn.dispatchEvent(new MouseEvent('click', opts));
                
                // Simulate pressing Enter (standard for div[role="button"])
                btn.dispatchEvent(new KeyboardEvent('keydown', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true, cancelable: true }));
                btn.dispatchEvent(new KeyboardEvent('keyup', { key: 'Enter', code: 'Enter', keyCode: 13, bubbles: true, cancelable: true }));
                
                clicked++; 
            } catch(e) {}
        }
    });
    
    if (clicked > 0 || attempts === 1 || attempts % 30 === 0) {
        console.log(`[VLI Bridge] Extraction trigger met (Clicked: ${clicked}, Attempt: ${attempts}).`);
        
        // Wait for the UI to render the expanded details
        setTimeout(() => {
            console.log("[VLI Bridge] Extracting DOM state...");
            let html = document.body.innerHTML;
            
            // Extract Deep Text from Shadow DOMs and append it to the payload
            console.log("[VLI Bridge] Piercing Shadow DOMs for hidden text...");
            const deepText = extractDeepText(document.body);
            html += `<div id="vli-deep-text" style="display:none;">${deepText}</div>`;
            
            // Only send if it looks like the portfolio page is loaded
            if (html.includes('gridRow') || html.includes('Activity') || html.includes('Orders')) {
                console.log("[VLI Bridge] Sending DOM payload to VLI backend (Size: " + html.length + " bytes)");
                
                chrome.runtime.sendMessage({
                    type: 'SYNC_DOM',
                    sourceUrl: window.location.href,
                    html: html
                }, response => {
                    if (response && response.success) {
                        console.log("[VLI Bridge] Backend response:", response.data);
                    } else {
                        console.error("[VLI Bridge] Backend sync failed:", response ? response.error : chrome.runtime.lastError);
                    }
                });
            } else {
                console.log("[VLI Bridge] Did not detect order grid. Skipping sync.");
            }
        }, 6000); // Wait 6 seconds for Angular XHR details to render
    }
}, 2000);
