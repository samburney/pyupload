/* Misc. helper functions for pyupload frontend */

const breakpoints = [640, 768, 1024, 1280, 1536, 1920, 2560];

// Debounce rapid repeated events events
function debounce(func, delay) {
    let timer;
    return function() {
        clearTimeout(timer);
        timer = setTimeout(() => func.apply(this, arguments), delay);
    };
}

// Calculate constrained display dimensions for an image
function calculateDisplaySize(naturalW, naturalH, container=window, ignore_height=false) {
    // Determine padding based on breakpoint
    let padding = 16; // Default for <sm
    if (window.innerWidth >= 640) padding = 32;

    // Calculate max dimensions based on container size and padding
    let maxW, maxH;
    if (container === window) {
        maxW = window.innerWidth - padding;
        maxH = window.innerHeight - padding;
    } else {
        maxW = container.clientWidth - padding;
        maxH = container.clientHeight - padding;
    }
    let w = naturalW;
    let h = naturalH;

    // Scale down if wider than container
    if (w > maxW) {
        h = (maxW / w) * h;
        w = maxW;
    }

    // Scale down if taller than container
    if (h > maxH && !ignore_height) {
        w = (maxH / h) * w;
        h = maxH;
    }

    return { width: parseInt(w), height: parseInt(h) };
}

// Calculate image request size snapped to nearest breakpoint
function calculateMaxImageSize(naturalW, naturalH, container=window, ignore_height=false) {
    const { width: displayW } = calculateDisplaySize(naturalW, naturalH, container, ignore_height);

    // Snap up to nearest breakpoint
    let w = displayW;
    for (let i = 0; i < breakpoints.length; i++) {
        if (w <= breakpoints[i]) {
            w = breakpoints[i];
            break;
        }
    }

    // Don't exceed natural width
    w = Math.min(w, naturalW);
    let h = parseInt((w / naturalW) * naturalH);

    return { width: w, height: h };
}

// Store client dimensions in a cookie for use in server-side rendering optimizations
function storeClientDimensions() {
    const params = new URLSearchParams();
    params.append('width', window.innerWidth);
    params.append('height', window.innerHeight);

    let cookieData = JSON.stringify({window_width: window.innerWidth, window_height: window.innerHeight});

    document.cookie = `window_dimensions=${cookieData}; path=/; max-age=${365*24*60*60}; samesite=lax`;
}

// Present sweetalert2 confirmation dialog
function sweetConfirm(el, config) {
    Swal.fire(config)
        .then((result) => {
            if (result.isConfirmed) {
                el.dispatchEvent(new Event('confirmed'));
            }
        });
}

function formatFileSize(bytes) {
    if (bytes < 1024) return bytes + ' B';
    if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
    if (bytes < 1073741824) return (bytes / 1048576).toFixed(1) + ' MB';
    return (bytes / 1073741824).toFixed(1) + ' GB';
}
