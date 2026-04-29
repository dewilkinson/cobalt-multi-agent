// inject.js
// Runs in the MAIN world to patch fetch and XHR without violating inline script CSPs
(function() {
    console.log("[VLI Bridge] MAIN world interceptor initializing...");

    const originalFetch = window.fetch;
    window.fetch = async function(...args) {
        const response = await originalFetch.apply(this, args);
        try {
            const clone = response.clone();
            const url = args[0] && typeof args[0] === 'string' ? args[0] : (args[0] && args[0].url ? args[0].url : '');
            
            if (url && (url.includes('activity') || url.includes('orders') || url.includes('history'))) {
                clone.json().then(data => {
                    window.postMessage({
                        type: 'FIDELITY_VLI_INTERCEPT',
                        url: url,
                        data: data
                    }, '*');
                }).catch(e => {});
            }
        } catch (e) { }
        return response;
    };

    const originalOpen = XMLHttpRequest.prototype.open;
    XMLHttpRequest.prototype.open = function(method, url, ...rest) {
        this._url = url;
        return originalOpen.call(this, method, url, ...rest);
    };

    const originalSend = XMLHttpRequest.prototype.send;
    XMLHttpRequest.prototype.send = function(...rest) {
        this.addEventListener('load', function() {
            if (this._url && (this._url.includes('activity') || this._url.includes('orders') || this._url.includes('history'))) {
                try {
                    const ct = this.getResponseHeader('content-type') || '';
                    if (ct.includes('json')) {
                        const data = JSON.parse(this.responseText);
                        window.postMessage({
                            type: 'FIDELITY_VLI_INTERCEPT',
                            url: this._url,
                            data: data
                        }, '*');
                    }
                } catch(e) {}
            }
        });
        return originalSend.apply(this, rest);
    };
    
    console.log("[VLI Bridge] MAIN world interceptor installed.");
})();
