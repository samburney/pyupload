/* Alpine JS handlers for Dropzone.js events */
document.addEventListener('alpine:init', () => {
    const uploadFormElement = document.getElementById("upload-form");

    Alpine.data('fileUploadWidget', () => ({
        dzInst: null,
        isLoaded: false,
        fileCount: 0,
        pendingCount: 0,
        uploadingCount: 0,
        queueLength: 0,
        totalUploadProgress: 0,
        erroredFiles: {},
        queueComplete: false,

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

                // If this isn't an image, replace thumbnail preview with our usual extension <div>
                if (!file.type.startsWith('image/')) {
                    const ext = file.name.includes('.') ? `.${file.name.split('.').pop()}` : '';

                    let thumbnailContainerDiv = document.createElement("div");
                    thumbnailContainerDiv.classList.add(
                        "rounded-sm", "min-w-13", "min-h-13", "shadow-sm", "border", "border-gray-300", "p-0.5",
                    );

                    let thumbnailDiv = document.createElement("div");
                    thumbnailDiv.classList.add(
                        "flex", "w-full", "h-full", "border", "border-dashed",
                        "rounded-sm", "text-gray-600", "border-gray-300", "bg-white",
                    );

                    let extDiv = document.createElement("div")
                    extDiv.classList.add("flex", "items-end", "justify-end", "h-full", "w-full", "p-1", "text-xs");
                    extDiv.textContent = ext;

                    thumbnailContainerDiv.append(thumbnailDiv);
                    thumbnailDiv.append(extDiv);

                    file.previewElement.querySelector('[data-dz-thumbnail]').replaceWith(thumbnailContainerDiv);
                }

                this.fileCount++;
                this._updateCounts();
            });

            this.dzInst.on("success", (file, response) => {
                console.log(`success: ${file.name}, ${response}`);

                const elt = file.previewElement.querySelector("[data-dz-uploadprogress]");
                elt.classList.replace("bg-blue-500", "bg-green-500");
            });

            this.dzInst.on("error", (file, errorMessage) => {
                console.log(`error: ${file.name}, ${errorMessage}`);

                const elt = file.previewElement.querySelector("[data-dz-uploadprogress]");
                elt.classList.replace("bg-blue-500", "bg-red-500");
                elt.style.width = "100%";

                this.erroredFiles[file.upload.uuid] = errorMessage;

                iziToast.error({
                    title: "Error",
                    message: `${file.name}: ${errorMessage}`,
                    progressBarColor: "red",
                    timeout: 30000,
                    animateInside: false,
                    drag: false,
                })
            });

            this.dzInst.on("removedfile", (file) => {
                if (Object.keys(this.erroredFiles).includes(file.upload.uuid)) {
                    delete this.erroredFiles[file.upload.uuid];
                }

                if (this.fileCount >= 1) {
                    this.fileCount--;
                }
                this._updateCounts();

                if (this.fileCount === 0) {
                    this.resetQueue();
                }
            });

            this.dzInst.on("complete", (file) => {
                console.log(`complete: ${file.name}`);

                this._updateCounts();
                if (this.queueLength > 0) {
                    this.dzInst.processQueue();
                }
            });

            this.dzInst.on("queuecomplete", () => {
                console.log(`queuecomplete`);

                this.queueComplete = true;
            });

            this.dzInst.on("processing", (file) => {
                console.log(`processing: ${file.name}`);
                this._updateCounts();
            });

            this.dzInst.on("uploadprogress", (file, progress, bytesSent) => {
                console.log(`uploadprogress: ${file.name} ${progress} ${bytesSent}`);
            });

            this.dzInst.on("totaluploadprogress", (totalUploadProgress, totalBytes, totalBytesSent) => {
                console.log(`totaluploadprogress: ${totalUploadProgress} ${totalBytes} ${totalBytesSent}`);
                this.totalUploadProgress = totalUploadProgress;
            });

            this.dzInst.on("paste", (elt) => {
                console.log(`paste: ${elt}`)
            });

            this.isLoaded = true;
        },
 
        // Handle paste events
        handlePaste(event) {
            const pasteDate = new Date(Date.now())
            const fileNamePasteDate = pasteDate.toISOString().slice(0, 19).replace(/[-:T]/g, "");
            const fileNameSuffix = `${fileNamePasteDate}${String(this.queueLength).padStart(2, "0")}`
            const items = event.clipboardData.items;

            for (let item of items) {
                // Files and binary data
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

        _updateCounts() {
            this.pendingCount = this.dzInst.getAddedFiles().length + this.dzInst.getQueuedFiles().length;
            this.uploadingCount = this.dzInst.files.filter(f => f.status === Dropzone.UPLOADING).length;
            this.queueLength = this.pendingCount + this.uploadingCount;
        },

        // Reset queue status
        resetQueue() {
            this.queueComplete = false;
            this.totalUploadProgress = 0;
        },

        // Begin processing pending uploads
        processUploads() {
            this.resetQueue();
            this.dzInst.processQueue();
        },
   }));
});
