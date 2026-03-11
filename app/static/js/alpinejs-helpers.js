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

    // Handle selecting uploads on multi-upload pages
    Alpine.data('handleSelectedUploads', () => ({
        superSelected: false,
        selectedIds: [],
        pulse: false,

        // selectedCount Getter for immediate updates
        get selectedCount() {
            return this.selectedIds.length;
        },

        // x-data init
        init() {
            // This watcher triggers every time an ID is added or removed
            this.$watch('selectedIds', () => {
                if (this.selectedCount >= 1) {
                    this.triggerPulse();
                }
            });
        },

        // Pulse the selected count when it changes to draw attention to it
        triggerPulse() {
            this.pulse = true;
            // 200ms matches a standard 'fast' CSS transition
            setTimeout(() => {
                this.pulse = false;
            }, 200);
        },

        // Clear current selections
        clearSelection() {
            this.selectedIds = [];
            this.superSelected = false;
        },

        // Toggle a selection by ID
        toggleSelected(id) {
            const idStr = id.toString();

            // Validate ID list and remove if found
            if (this.selectedIds.includes(idStr)) {
                this.selectedIds = this.selectedIds.filter(i => i !== idStr);
            }
            // Otherwise, add to ID to the list
            else {
                this.selectedIds.push(idStr);
            }
        },

        // Handle selectAll() button; currently just calls `selectAllVisible()`
        selectAll() {
            this.selectAllVisible();
        },

        // Select all visible
        selectAllVisible() {
            // Query the DOM for all checkboxes
            const allCheckboxes = Array.from(document.querySelectorAll('input[name="selected_upload_ids"]'));
            const visibleIds = allCheckboxes.map(cb => cb.value);
            
            // Merge with selectedIds
            const combined = new Set([...this.selectedIds, ...visibleIds]);

            // Apply new merged list
            this.selectedIds = Array.from(combined);
        }
    }))

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
