
        document.addEventListener("DOMContentLoaded", () => {
            const verSpan = document.getElementById('vli-watermark-version');
            if (verSpan) verSpan.innerText = typeof VLI_CLIENT_VERSION !== 'undefined' ? VLI_CLIENT_VERSION : 'Unknown';
        });
    