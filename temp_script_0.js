
        // VLI Dynamic Tab Session Tracker (Window Isolation)
        const VLI_CLIENT_ID = sessionStorage.getItem('vli_client_id') || ('client_' + Math.random().toString(36).substr(2, 9));
        sessionStorage.setItem('vli_client_id', VLI_CLIENT_ID);
        
        // Globally intercept fetch to attach Client-ID header to internal VLI requests
        const originalFetch = window.fetch.bind(window);
        window.fetch = async function (...args) {
            let [resource, config] = args;
            if(typeof resource === 'string' && resource.startsWith('/api/vli/')) {
                config = config || {};
                config.headers = config.headers || {};
                config.headers['X-VLI-Client-ID'] = VLI_CLIENT_ID;
                return originalFetch(resource, config);
            }
            return originalFetch(...args);
        };

        // Centralized Version Control
        const VLI_CLIENT_VERSION = "00.000.0070";
    