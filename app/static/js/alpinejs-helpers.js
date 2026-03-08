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

    // Upload widget store
    Alpine.store('uploadWidget', {
        files: [],
        dragActive: false,

        addFiles(fileList) {
            this.files = [...this.files, ...Array.from(fileList)];
            this.dragActive = false;
            this.updateFileInput();
        },

        removeFile(index) {
            this.files.splice(index, 1);
            this.updateFileInput();
        },

        handleDrop(event) {
            this.addFiles(event.dataTransfer.files);
        },

        updateFileInput() {
            const dt = new DataTransfer();
            this.files.forEach(file => dt.items.add(file));
            const input = document.getElementById('file-upload-picker');
            if (input) input.files = dt.files;
        },

        formatFileSize(bytes) {
            if (bytes < 1024) return bytes + ' B';
            if (bytes < 1048576) return (bytes / 1024).toFixed(1) + ' KB';
            return (bytes / 1048576).toFixed(1) + ' MB';
        }
    });

    // Clipboard magic for share button
    Alpine.magic('clipboard', () => {
        return subject => navigator.clipboard.writeText(subject)
    })
});
