/* Javascript supports for gallery multiselect functionality */

document.addEventListener('alpine:init', () => {
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
        sidebarLoaded: false,

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

            setTimeout(() => {
                this.pulse = false;
            }, 200);  // 200ms matches a standard 'fast' CSS transition
        },

        // Reset everything to defaults when nothing is selected
        resetSelection() {
            // Reset state to defaults
            this.superSelected = false;
            this.allVisibleSelected = false;
            this.deselectedIds = [];
            this.previousSelectedIds = [];
            this.preSuperSelectedIds = [];
            this.sidebarLoaded = false;

            // Reset sidebar element to defaults
            htmx.find("#gallery-sidebar").innerHTML = "";
            htmx.find("#gallery-sidebar").classList.add('sidebar-not-loaded');
        },

        // Clear current selections
        clearSelection() {
            this.selectedIds = [];
            this.resetSelection();
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
            this.triggerServerUpdate();
        },

        // Disable Super Select mode and restore original selections
        disableSuperSelect() {
            this.superSelected = false;
            this.deselectedIds = [];

            // Restore original item selection
            // Also causes this.triggerServerUpdate() to be called
            this.selectedIds = [...this.preSuperSelectedIds];
        },

        // Trigger HTMX swaps
        triggerServerUpdate() {
            htmx.trigger('#sidebar-request-trigger', 'update-sidebar');
        },

        // x-data init
        init() {
            // Watch every time an upload id is added or removed
            this.$watch('selectedIds', () => {
                // Trigger pulse effect
                if (this.selectedCount >= 1) {
                    this.triggerPulse();

                    // Trigger server update, which will update sidebar content
                    this.triggerServerUpdate();
                }

                // Remove contents of sidebar
                else {
                    this.resetSelection();
                }

                // Force refresh of allVisibleSelected
                this.updateAllVisibleSelected();
            });

            // Watch for HTMX swaps
            document.addEventListener('htmx:afterSwap', (event) => {
                // Pagination events
                if (event.target.id == 'gallery-grid') {
                    // If superSelect enabled, immediately select all visible
                    if (this.superSelected) {
                        this.selectAllVisible(this.deselectedIds);
                    }
                }

                // Track HTMX request to load initial sidebar content
                // We show the skeleton on first load and fade content in, but just show a simple
                // loading spinner on subsequent events.
                if (event.target.id == 'gallery-sidebar' && event.detail.requestConfig.triggeringEvent.type == 'update-sidebar') {
                    // If sidebar not loaded yet, wait for transition then remove `sidebar-not-loaded` class
                    if (!this.sidebarLoaded) {
                        setTimeout(() => {
                            this.sidebarLoaded = true;
                            event.target.classList.remove('sidebar-not-loaded');
                        }, 300); // match CSS transition duration
                    }
                    // If it is loaded, remove immediately
                    else {
                        event.target.classList.remove('sidebar-not-loaded');
                    }
                }

                // Force refresh of allVisibleSelected
                this.updateAllVisibleSelected();
            });

            // Update once on first init to catch items selected when the page was rendered
            this.updateAllVisibleSelected();

            /* TODO: THIS ABSOLUTELY MUST BE REMOVED BEFORE MERGE!! */
            // Temporary for dev use
            this.selectedIds = ['338', '327'];
            this.$nextTick(() => this.triggerServerUpdate());
        }
    }))
});
