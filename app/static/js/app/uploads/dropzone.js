///* Dropzone configuration */
//document.addEventListener("DOMContentLoaded", () => {
//    const form = document.getElementById("upload-form");
//
//    // Dropzone configuration
//    Dropzone.options.uploadForm = {
//        paramName: "upload_files",
//        uploadMultiple: false,
//        maxFilesize: parseInt(form.dataset.maxFileSize, 10),
//        acceptedFiles: form.dataset.acceptedFiles || null,
//        autoProcessQueue: false,
//        clickable: ["#browse-files-button"],
//        previewTemplate: document.querySelector('#uploaded-file-item-template').innerHTML,
//        previewsContainer: document.querySelector('#uploaded-file-item-container')
//    }
//});

/* Alpine JS handlers for Dropzone.js events */
document.addEventListener('alpine:init', () => {
    const uploadFormElement = document.getElementById("upload-form");

    Alpine.data('fileUploadWidget', () => ({
        dzInst: null,
        statusMessage: 'Waiting for files...',
        fileCount: 0,

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
                this.fileCount++;
                this.statusMessage = `Added: ${file.name}`;
            });

            this.dzInst.on("success", (file, response) => {
                this.statusMessage = 'Upload successful!';
            });

            this.dzInst.on("error", (file, errorMessage) => {
                this.statusMessage = `Error: ${errorMessage}`;
            });

            this.dzInst.on("removedfile", (file) => {
                this.fileCount--;
                this.statusMessage = `Removed: ${file.name}`;
            });
        }
    }));
});
