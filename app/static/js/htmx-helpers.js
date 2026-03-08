/* HTMX helper functions for pyupload frontend */

// HTMX image swap handlers for resized image loading (used by view-frame and preview modal)
function setupImageSwapHandlers(elementId) {
    // Skip server request entirely when downsizing (existing larger image suffices)
    document.addEventListener('htmx:beforeRequest', function(event) {
        const target = event.detail.elt;
        if (target.id !== elementId) return;

        const currentLoadedWidth = parseInt(target.dataset.loadedWidth || '0');
        if (currentLoadedWidth <= 0) return; // Initial load — always fetch

        const requestedWidth = parseInt(event.detail.requestConfig.parameters.width || '0');
        if (requestedWidth > 0 && requestedWidth <= currentLoadedWidth) {
            event.preventDefault();
        }
    });

    // Prevent FOUC: preload new image before updating DOM
    document.addEventListener('htmx:beforeSwap', function(event) {
        const target = event.detail.target;
        if (target.id !== elementId) return;
        event.detail.shouldSwap = false;

        const tmp = document.createElement('div');
        tmp.innerHTML = event.detail.serverResponse;
        const newContainer = tmp.firstElementChild;
        const newImg = tmp.querySelector('img');
        if (!newImg) return;

        const currentImg = target.querySelector('img');
        const newSrc = newImg.getAttribute('src');
        const newLoadedWidth = newContainer?.dataset?.loadedWidth;

        // Skip entirely if src is identical
        if (currentImg && currentImg.getAttribute('src') === newSrc) return;

        const preloader = new Image();
        const parent = target.parentElement;
        const applyUpdate = function() {
            if (currentImg) {
                // Resize: update src and loaded-width in place (preloader cache hit)
                if (newLoadedWidth) target.dataset.loadedWidth = newLoadedWidth;
                currentImg.setAttribute('src', newSrc);
            } else {
                // Initial load from placeholder — pin parent size during swap to prevent collapse
                const rect = target.getBoundingClientRect();
                parent.style.minWidth = rect.width + 'px';
                parent.style.minHeight = rect.height + 'px';

                const tempDiv = document.createElement('div');
                tempDiv.innerHTML = event.detail.serverResponse;
                const newElement = tempDiv.firstElementChild;
                target.after(newElement);
                requestAnimationFrame(() => {
                    target.remove();
                    htmx.process(newElement);
                    requestAnimationFrame(() => {
                        // Clear pinned size after swap
                        parent.style.minWidth = '';
                        parent.style.minHeight = '';
                        parent.style.width = '';
                        parent.style.height = '';
                    });
                });
            }
        };
        preloader.onload = applyUpdate;
        preloader.onerror = applyUpdate;
        preloader.src = newSrc;
    });
}
