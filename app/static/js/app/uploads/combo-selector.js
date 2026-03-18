document.addEventListener('alpine:init', () => {
    Alpine.data('multiSelectCombo', () => ({
        menu: false,
        search: '',
        selected: [],
        isNewCollection: false,

        init() {
            this.selected = Array.from(
                this.$el.querySelectorAll('input[name=collection_ids][checked]')
                ).map(el => el.value)

            this.$watch('search', value => {
                const trimmed = value.trim().toLowerCase();
                const labels = Array.from(this.$el.querySelectorAll('ul#collections-combo-selector-options li.menu-item label'));
                const exactMatch = labels.some(label => label.textContent.trim().toLowerCase() === trimmed);
                this.isNewCollection = trimmed !== '' && !exactMatch;
            })
        },

        get buttonText() {
            if (this.selected.length > 0) {
                if (this.selected.length == 1) {
                    return this.$refs['collection-' + this.selected[0]].nextSibling.textContent.trim();
                }
                else {
                    return this.selected.length + ' selected';
                }
            }
            else {
                return '0 selected';
            }
        }
    }))
})
