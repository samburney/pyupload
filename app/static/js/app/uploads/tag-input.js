document.addEventListener('alpine:init', () => {
    Alpine.data('tagInput', () => ({
        menu: false,
        newTag: '',

        update() {
            if (this.newTag.trim() === '') {
                this.menu = false;
            }
            else {
                this.menu = true;
            }
        }
    }))
})
