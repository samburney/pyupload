/* HTMX helper functions for pyupload frontend */

// HTMX beforeRequest handlers
document.addEventListener('htmx:beforeRequest', function(event) {
    const requestConfig = event.detail.requestConfig;
    const triggeringElement = event.detail.elt;
    const triggeringEvent = requestConfig.triggeringEvent;
    const eventType = triggeringEvent?.type;

    // Image frame resizing handlers
    if ((triggeringElement.id == 'view-frame-image' || triggeringElement.id == 'view-modal-image') && eventType === 'resize') {
        // Skip server request entirely when downsizing (existing larger image suffices)
        const currentLoadedWidth = parseInt(triggeringElement.dataset.loadedWidth || '0');
        const requestedWidth = parseInt(event.detail.requestConfig.parameters.width || '0');
        if (requestedWidth > 0 && requestedWidth <= currentLoadedWidth) {
            event.preventDefault();
        }
    }
});

// HTMX beforeSwap handlers
document.addEventListener('htmx:beforeSwap', function(event) {
    const requestConfig = event.detail.requestConfig;
    const triggeringElement = event.detail.elt;
    const triggeringEvent = requestConfig.triggeringEvent;
    const eventType = triggeringEvent?.type;

    // Image frame event handlers
    if (triggeringElement.id == 'view-frame-image') {
        // Remove dimensions hardcoded in server-side template after image load
        let positionLocator = triggeringElement.closest('.image-position-locator');
        if (positionLocator) {
            positionLocator.style.width = '';
            positionLocator.style.height = '';
        }
    }
});
