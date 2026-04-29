// background.js
// Runs as a Service Worker to bypass webpage CSP restrictions for fetch

chrome.runtime.onMessage.addListener((message, sender, sendResponse) => {
    if (message.type === 'SYNC_DOM') {
        console.log("[VLI Bridge SW] Received DOM payload from content script. Forwarding to backend...");
        
        fetch('http://127.0.0.1:8000/api/fidelity/sync', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                sourceUrl: message.sourceUrl,
                payloadType: 'dom',
                html: message.html
            })
        })
        .then(r => r.json())
        .then(res => {
            console.log("[VLI Bridge SW] Backend sync successful:", res);
            sendResponse({ success: true, data: res });
        })
        .catch(e => {
            console.error("[VLI Bridge SW] Backend sync failed:", e);
            sendResponse({ success: false, error: String(e) });
        });
        
        // Return true to indicate we will call sendResponse asynchronously
        return true;
    }
});
