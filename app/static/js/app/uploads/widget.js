/* Alpine JS handlers for Dropzone.js events */
document.addEventListener('alpine:init', () => {
    const uploadFormElement = document.getElementById('upload-form');

    Alpine.data('fileUploadWidget', () => ({
        dzInst: null,
        isLoaded: false,
        fileCount: 0,
        pendingCount: 0,
        uploadingCount: 0,
        queueLength: 0,
        totalUploadProgress: 0,
        successfulFiles: {},
        erroredFiles: {},
        queueComplete: false,

        init() {
            // Create Dropzone instance
            this.dzInst = new Dropzone(uploadFormElement, {
                paramName: 'upload_files',
                uploadMultiple: false,
                maxFilesize: parseInt(uploadFormElement.dataset.maxFileSize, 10),
                acceptedFiles: uploadFormElement.dataset.acceptedFiles || null,
                autoProcessQueue: false,
                clickable: ['#browse-files-button'],
                previewTemplate: document.querySelector('#uploaded-file-item-template').innerHTML,
                previewsContainer: document.querySelector('#uploaded-file-item-container'),
                thumbnailMethod: 'contain',
            });

            this.dzInst.on('addedfile', (file) => {
                file.previewElement.querySelector('[data-dz-size]').textContent = formatFileSize(file.size);
                file.previewElement.querySelector('[data-dz-type]').textContent = file.type;

                // If this isn't an image, replace thumbnail preview with our usual extension <div>
                if (!file.type.startsWith('image/')) {
                    const ext = (file.name.includes('.') ? `.${file.name.split('.').pop()}` : '').substring(0, 6);
                    const templateElt = document.querySelector('#uploaded-file-item-thumbnail-file');
                    const thumbnailElt = templateElt.content.cloneNode(true).querySelector('[data-dz-thumbnail]');

                    thumbnailElt.querySelector('[data-dz-thumbnail-ext]').textContent = ext;

                    file.previewElement.querySelector('[data-dz-thumbnail-container]').replaceWith(thumbnailElt);
                }

                this.fileCount++;
                this._updateCounts();
            });

            this.dzInst.on('thumbnail', (file, dataUrl) => {
                const placeholderElt = file.previewElement.querySelector('[data-dz-thumbnail-placeholder]');
                const templateElt = document.querySelector('#uploaded-file-item-thumbnail-image');
                const thumbnailElt = templateElt.content.cloneNode(true).querySelector('[data-dz-thumbnail]');

                thumbnailElt.src = dataUrl;
                placeholderElt.replaceWith(thumbnailElt);
            });

            this.dzInst.on('success', (file, response) => {
                // Process response.  The upload endpoint can handle multiple uploads, but since we only ever send
                // one at a time, we just need to grab the first result.
                const result = response[0];
                const uploadStatus = result['status'];

                // Handle successful response
                if (uploadStatus === 'success') {
                    const uploadProgressElt = file.previewElement.querySelector('[data-dz-uploadprogress]');
                    uploadProgressElt.classList.replace('bg-blue-500', 'bg-green-500');

                    // Trigger HTMX `refresh-content` listener
                    htmx.trigger(document.body, 'refresh-content');

                    // Update upload list element
                    const fileNameElt = file.previewElement.querySelector('[data-dz-name]');
                    const fileNameAnchor = document.createElement('a');

                    fileNameAnchor.classList.add('hover:underline');
                    fileNameAnchor.setAttribute('href', result['view_url']);
                    fileNameAnchor.setAttribute('title', file.name);
                    fileNameAnchor.textContent = file.name;

                    fileNameElt.replaceChildren(fileNameAnchor);

                    this.successfulFiles[file.upload.uuid] = file;
                }

                // Otherwise, handle as an error
                else {
                    this._handleError(file, result.message);
                }
            });

            this.dzInst.on('error', (file, errorMessage) => {
                this._handleError(file, errorMessage);
            });

            this.dzInst.on('removedfile', (file) => {
                if (Object.keys(this.successfulFiles).includes(file.upload.uuid)) {
                    delete this.successfulFiles[file.upload.uuid];
                }

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

            this.dzInst.on('complete', (file) => {
                this._updateCounts();
                if (this.queueLength > 0) {
                    this.dzInst.processQueue();
                }
            });

            this.dzInst.on('queuecomplete', () => {

                const successCount = Object.keys(this.successfulFiles).length;

                if (successCount > 0) {
                    iziToast.success({
                        title: 'Info',
                        message: `${successCount} files successfully uploaded`,
                        progressBarColor: 'green',
                        timeout: 30000,
                        animateInside: false,
                        drag: false,
                    });
                };

                this.queueComplete = true;
            });

            this.dzInst.on('processing', (file) => {
                this._updateCounts();
            });

            this.dzInst.on('totaluploadprogress', (totalUploadProgress, totalBytes, totalBytesSent) => {
                this.totalUploadProgress = totalUploadProgress;
            });

            this.isLoaded = true;
        },

        // Handle paste events
        handlePaste(event) {
            const pasteDate = new Date(Date.now());
            const fileNamePasteDate = pasteDate.toISOString().slice(0, 19).replace(/[-:T]/g, '');
            const fileNameSuffix = `${fileNamePasteDate}${String(this.queueLength).padStart(2, '0')}`;
            let items = event.clipboardData.items;

            // Handle blob/text mix (Discard text)
            if (items.length > 1) {
                let blobItems = [];

                for (let item of items) {
                    if (item.kind === 'file') {
                        blobItems.push(item);
                    }
                }

                if (blobItems.length > 0) {
                    items = blobItems;
                }
            }

            for (let item of items) {
                // Files and binary data
                if (item.kind === 'file') {
                    const blob = item.getAsFile();
                    let file = null;

                    // Handle direct image paste
                    if (blob.name.startsWith('image.') && item.type.startsWith('image')) {
                        const mimeSplit = item.type.split('/');
                        const name = `pasted-${mimeSplit[0]}-${fileNameSuffix}`;
                        const ext = mimeSplit[1] === 'jpeg' ? 'jpg' : mimeSplit[1];

                        file = new File([blob], `${name}.${ext}`, { type: item.type });
                    }
                    else {
                        file = blob;
                    }

                    this.dzInst.addFile(file);
                }
                // Text / HTML
                else if (item.kind === 'string' && ['text/plain', 'text/html'].includes(item.type)) {
                    const itemType = item.type;
                    item.getAsString((text) => {
                        const ext = itemType === 'text/html' ? 'html' : 'txt';
                        const file = new File([text], `pasted-text-${fileNameSuffix}.${ext}`, { type: itemType });
                        this.dzInst.addFile(file);
                    });
                }
                else {
                    console.debug(`Received unhandled data type: ${item.kind}:${item.type}`);
                }
            }
        },

        _updateCounts() {
            this.pendingCount = this.dzInst.getAddedFiles().length + this.dzInst.getQueuedFiles().length;
            this.uploadingCount = this.dzInst.files.filter(f => f.status === Dropzone.UPLOADING).length;
            this.queueLength = this.pendingCount + this.uploadingCount;

            if (this.uploadingCount === 0) {
                this.totalUploadProgress = 0;
            }
        },

        _handleError(file, errorMessage) {
            const elt = file.previewElement.querySelector('[data-dz-uploadprogress]');
            elt.classList.replace('bg-blue-500', 'bg-red-500');
            elt.style.width = '100%';

            this.erroredFiles[file.upload.uuid] = errorMessage;

            iziToast.error({
                title: 'Error',
                message: `${file.name}: ${errorMessage}`,
                progressBarColor: 'red',
                timeout: 30000,
                animateInside: false,
                drag: false,
            });
        },

        // Reset queue status
        resetQueue() {
            this.successfulFiles = {};
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
