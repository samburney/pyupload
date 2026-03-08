// Add event handlers to store dimensions on load and resize
window.addEventListener('load', function() {
    storeClientDimensions();
});
window.addEventListener('resize', debounce(storeClientDimensions, 200));
