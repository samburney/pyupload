/* Alpine JS handlers for Dropzone.js events */
document.addEventListener('alpine:init', () => {
    const uploadFormElement = document.getElementById("upload-form");

    Alpine.data('fileUploadWidget', () => ({
        dzInst: null,
        isLoaded: false,
        statusMessage: 'Waiting for files...',
        fileCount: 0,
        pendingCount: 0,
        queueLength: 0,

        init() {
            // Create Dropzone instance
            this.dzInst = new Dropzone(uploadFormElement, {
                paramName: "upload_files",
                uploadMultiple: false,
                maxFilesize: parseInt(uploadFormElement.dataset.maxFileSize, 10),
                acceptedFiles: uploadFormElement.dataset.acceptedFiles || null,
                autoProcessQueue: false,
                clickable: ["#browse-files-button"],
                previewTemplate: document.querySelector('#uploaded-file-item-template').innerHTML,
                previewsContainer: document.querySelector('#uploaded-file-item-container'),
            });

            this.dzInst.on("addedfile", (file) => {
                file.previewElement.querySelector('[data-dz-size]').textContent = formatFileSize(file.size);
                file.previewElement.querySelector('[data-dz-type]').textContent = file.type;
                this.fileCount++;
                this.pendingCount = this.dzInst.getAddedFiles().length;
                this.queueLength = this.pendingCount + this.dzInst.getActiveFiles().length;
            });

            this.dzInst.on("success", (file, response) => {
                this.statusMessage = 'Upload successful!';
            });

            this.dzInst.on("error", (file, errorMessage) => {
                this.statusMessage = `Error: ${errorMessage}`;
            });

            this.dzInst.on("removedfile", (file) => {
                if (this.fileCount >= 1) {
                    this.fileCount--;
                }
                this.pendingCount = this.dzInst.getAddedFiles().length;
                this.queueLength = this.pendingCount + this.dzInst.getActiveFiles().length;
            });

            this.dzInst.on("complete", (file) => {
                this.pendingCount = this.dzInst.getAddedFiles().length;
                this.queueLength = this.pendingCount + this.dzInst.getActiveFiles().length;
                if (this.queueLength > 0) {
                    this.dzInst.processQueue();
                }
            });

            this.isLoaded = true;
        },
    }));
});
