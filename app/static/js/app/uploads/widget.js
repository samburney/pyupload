/* Alpine JS handlers for Dropzone.js events */
document.addEventListener('alpine:init', () => {
    const uploadFormElement = document.getElementById("upload-form");

    Alpine.data('fileUploadWidget', () => ({
        dzInst: null,
        isLoaded: false,
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
                thumbnailMethod: "contain",
            });

            this.dzInst.on("addedfile", (file) => {
                file.previewElement.querySelector('[data-dz-size]').textContent = formatFileSize(file.size);
                file.previewElement.querySelector('[data-dz-type]').textContent = file.type;
                this.fileCount++;
                this.pendingCount = this.dzInst.getAddedFiles().length;
                this.queueLength = this.pendingCount + this.dzInst.getActiveFiles().length;
            });

            this.dzInst.on("success", (file, response) => {
            });

            this.dzInst.on("error", (file, errorMessage) => {
            });

            this.dzInst.on("removedfile", (file) => {
                if (this.fileCount >= 1) {
                    this.fileCount--;
                }
                this.pendingCount = this.dzInst.getAddedFiles().length;
                this.queueLength = this.pendingCount + this.dzInst.getActiveFiles().length;
            });

            this.dzInst.on("complete", (file) => {
                console.log(`complete: ${file.name}`);

                this.pendingCount = this.dzInst.getAddedFiles().length;
                this.queueLength = this.pendingCount + this.dzInst.getActiveFiles().length;
                if (this.queueLength > 0) {
                    this.dzInst.processQueue();
                }
            });

            this.dzInst.on("queuecomplete", () => {
                console.log(`queuecomplete`);
            });

            this.dzInst.on("processing", (file) => {
                console.log(`processing: ${file.name}`);
            });

            this.dzInst.on("uploadprogress", (file, progress, bytesSent) => {
                console.log(`uploadprogress: ${file.name} ${progress} ${bytesSent}`);
            });

            this.dzInst.on("totaluploadprogress", (totalUploadProgress, totalBytes, totalBytesSent) => {
                console.log(`totaluploadprogress: ${totalUploadProgress} ${totalBytes} ${totalBytesSent}`);
            });

            this.dzInst.on("paste", (elt) => {
                console.log(`paste: ${elt}`)
            });

            this.isLoaded = true;
        },
 
        handlePaste(event) {
            const pasteDate = new Date(Date.now())
            const fileNamePasteDate = pasteDate.toISOString().slice(0, 19).replace(/[-:T]/g, "");
            const fileNameSuffix = `${fileNamePasteDate}${String(this.queueLength).padStart(2, "0")}`
            const items = event.clipboardData.items;

            for (let item of items) {
                // File
                if (item.kind === "file") {
                    const blob = item.getAsFile();
                    let file = null;

                    // Handle direct image paste
                    if (blob.name.startsWith("image.") && item.type.startsWith("image")) {
                        const mimeSplit = item.type.split("/");
                        const name = `pasted-${mimeSplit[0]}-${fileNameSuffix}`
                        const ext = mimeSplit[1] === "jpeg" ? "jpg" : mimeSplit[1];

                        file = new File([blob], `${name}.${ext}`, { type: item.type});
                    }
                    else {
                        file = blob;
                    }

                    this.dzInst.addFile(file);
                }
                // Text / HTML
                else if (item.kind === "string" && ["text/plain", "text/html"].includes(item.type)) {
                    const itemType = item.type;
                    item.getAsString((text) => {
                        const ext = itemType === "text/html" ? "html" : "txt";
                        const file = new File([text], `pasted-text-${fileNameSuffix}.${ext}`, { type: itemType });
                        this.dzInst.addFile(file);
                    });
                }
                else {
                    console.debug(`Received unhandled data type: ${item.kind}:${item.type}`)
                }
            }
        },
   }));
});
