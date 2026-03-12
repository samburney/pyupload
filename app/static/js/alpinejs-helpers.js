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
        allVisibleSelected: false,
        selectedIds: [],
        deselectedIds: [],
        previousSelectedIds: [],
        preSuperSelectedIds: [],
        pulse: false,
        writableCount: 0,

        // Get list of visible upload checkboxes
        get visibleCheckboxes() {
            return Array.from(document.querySelectorAll('input[name="selected_upload_ids"]'));
        },

        // selectedCount Getter for immediate updates
        get selectedCount() {
            if (!this.superSelected) {
                return this.selectedIds.length;
            }
            else {
                return this.writableCount - this.deselectedIds.length;
            }
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
            this.superSelected = false;
            this.allVisibleSelected = false;
            this.selectedIds = [];
            this.deselectedIds = [];
            this.previousSelectedIds = [];
            this.preSuperSelectedIds = [];
        },

        // Toggle a selection by ID
        toggleSelected(id) {
            const idStr = id.toString();

            // Validate ID list and remove if found
            if (this.selectedIds.includes(idStr)) {
                this.selectedIds = this.selectedIds.filter(i => i !== idStr);

                // Add to deselected ID list
                this.deselectedIds.push(idStr);
            }
            // Otherwise, add to ID to the list
            else {
                this.selectedIds.push(idStr);

                // Remove from deselected ID list if present
                if (this.deselectedIds.includes(idStr)) {
                    this.deselectedIds = this.deselectedIds.filter(i => i !== idStr);
                }
            }
        },

        // Select all checkboxes in the DOM
        selectAllVisible(filter=[]) {
            // Query the DOM for all checkboxes
            const visibleIds = this.visibleCheckboxes.map(cb => cb.value);
            const filteredVisibleIds = visibleIds.filter(id => !filter.includes(id))
            
            // Merge with selectedIds
            const combined = new Set([...this.selectedIds, ...filteredVisibleIds]);

            // Apply new merged list
            this.selectedIds = Array.from(combined);
        },

        // Select all visible
        toggleSelectAllVisible() {
            // If we haven't selected all visible, do that now
            if (!this.allVisibleSelected) {
                const visibleIds = this.visibleCheckboxes.map(cb => cb.value);

                // Save current selection
                this.previousSelectedIds = [...this.selectedIds];

                // Remove any visible uploads from deselectedIds array
                this.deselectedIds = this.deselectedIds.filter(id => !visibleIds.includes(id));

                // Select all visible uploads
                this.selectAllVisible();
            }

            // Otherwise, restore previous selections
            else {
                this.selectedIds = [...this.previousSelectedIds];
                this.previousSelectedIds = [];
            }
        },

        // Determine if every visible check box is checked
        updateAllVisibleSelected() {
                this.allVisibleSelected = this.visibleCheckboxes.length && this.visibleCheckboxes.every(cb => this.selectedIds.includes(cb.value));
        },

        // Enable Super Select mode (Select all possible items including non-visible)
        enableSuperSelect() {
            // Save current item selection
            this.preSuperSelectedIds = [...this.selectedIds];

            this.superSelected = true;
        },

        // Disable Super Select mode and restore original selections
        disableSuperSelect () {
            // Restore original item selection
            this.selectedIds = [...this.preSuperSelectedIds];
            this.deselectedIds = [];

            this.superSelected = false;
        },

        // x-data init
        init() {
            // Watch every time an upload id is added or removed
            this.$watch('selectedIds', () => {
                // Trigger pulse effect
                if (this.selectedCount >= 1) {
                    this.triggerPulse();
                }

                // Force refresh of allVisibleSelected
                this.updateAllVisibleSelected();
            });

            // Watch for HTMX swaps
            document.addEventListener('htmx:afterSwap', () => {
                // If superSelect enabled, immediately select all visible
                if (this.superSelected) {
                    this.selectAllVisible(this.deselectedIds);
                }

                // Force refresh of allVisibleSelected
                this.updateAllVisibleSelected();
            });

            // Update once on first init to catch items selected when the page was rendered
            this.updateAllVisibleSelected();
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
