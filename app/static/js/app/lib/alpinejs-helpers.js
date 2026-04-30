/* Frontend helper functions for Alpine.js components */

document.addEventListener('alpine:init', () => {
    // Image placeholder resize hack
    Alpine.data('imagePlaceholder', (naturalW, naturalH, container=window, ignore_height=false) => ({
        width: 0,
        height: 0,
        ready: false,

        init() {
            this.calculateSize();
        },

        calculateSize() {
            const { width: w, height: h } = calculateDisplaySize(naturalW, naturalH, container, ignore_height);

            this.width = w;
            this.height = h;
            this.ready = true;
        }
    }));

    // Clipboard magic for share button
    Alpine.magic('clipboard', () => {
        return subject => navigator.clipboard.writeText(subject)
    })
});
