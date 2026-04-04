document.addEventListener('alpine:init', () => {
    Alpine.data('multiSelectCombo', () => ({
        menu: false,
        search: '',
        selected: [],
        partially_selected: [],
        isNewCollection: false,

        get buttonText() {
            let all_selected_count = this.selected.length + this.partially_selected.length

            if (all_selected_count > 0) {
                if (all_selected_count == 1 && this.selected.length == 1) {
                    return this.$refs['collection-' + this.selected[0]].nextSibling.textContent.trim();
                }
                else {
                    let selected_text = all_selected_count + ' selected'
                    let partially_selected_text = ''

                    if (this.partially_selected.length > 0) {
                        partially_selected_text = ' (' + this.partially_selected.length + ' partial)'
                    }

                    return selected_text + partially_selected_text;
                }
            }
            else {
                return this.selected.length + ' selected';
            }
        },

        refreshState() {
            this.selected = Array.from(
                this.$el.querySelectorAll('input[name=collection_ids][checked]:not([data-partial="true"])')
            ).map(el => el.value)

            this.partially_selected = Array.from(
                this.$el.querySelectorAll('input[name=collection_ids][data-partial="true"]')
            ).map(el => el.value)

        },

        init() {
            this.refreshState()

            this.$watch('search', value => {
                const trimmed = value.trim().toLowerCase();
                const labels = Array.from(this.$el.querySelectorAll('ul#collections-combo-selector-options li.menu-item label'));
                const exactMatch = labels.some(label => label.textContent.trim().toLowerCase() === trimmed);
                this.isNewCollection = trimmed !== '' && !exactMatch;
            })

            document.addEventListener('htmx:afterSwap', (event) => {
                if (event.detail.target.id === 'collections-combo-selector-options') {
                    this.refreshState()
                }
            });
        }
    }))
})
