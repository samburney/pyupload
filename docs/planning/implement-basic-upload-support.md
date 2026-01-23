# Core Upload Functionality Implementation Plan (Phase 1)

## Overview

Implement sequential batch file upload with on-demand thumbnail caching, following simplegallery's proven patterns. Files are named using date + UUID format, stored by user ID in the filesystem, and metadata is tracked in the legacy `uploads` and `images` tables.

**Scope**: File receive, validation, storage, and basic image metadata extraction (Phase 1).  
**Out of Scope**: Archive extraction, image thumbnail generation/caching, parallel batch processing, watermarking, EXIF extraction.

---

## Step 1: Create File Storage Abstraction Layer

**File**: `app/lib/file_storage.py` (new)

**Rationale**: Centralize file system operations, quota enforcement, and filename generation to avoid duplication across API and UI endpoints.

**Responsibilities**:
- Generate collision-free filenames using date + UUID format (`description_YYYYMMDD-HHMMSS-UUUUUUUU`)
- Validate filename/path for security (prevent path traversal)
- Construct config-driven file paths (files_dir from AppConfig)
- Enforce user quotas (max file size, max upload count)
- Manage filesystem operations (create directories, save/delete files)

**Acceptance Criteria**:
- [ ] Filename generation creates collision-proof names with date + UUID components
- [ ] Path construction uses files_dir config value and user_id
- [ ] Quota checking enforces user_max_file_size_mb and user_max_uploads limits
- [ ] File storage creates parent directories as needed
- [ ] Path validation prevents directory traversal attacks
- [ ] All functions have proper type hints and docstrings

**Estimated Effort**: 2-3 hours

---

## Step 2: Create Shared Upload Handler

**File**: `app/lib/upload_handler.py` (new)

**Rationale**: Centralize business logic for processing multiple files so both API and UI endpoints reuse identical logic.

**Responsibilities**:
- Process multiple files sequentially (Phase 1)
- Validate each file before storage (size, type, security)
- Enforce quotas per file and in aggregate
- Handle per-file errors without cascading
- Manage temporary file cleanup on errors
- Create Upload and Image records in database

**Acceptance Criteria**:
- [ ] Processes multiple files sequentially from list
- [ ] Validates each file independently (returns per-file results)
- [ ] Returns UploadResult array with success/error status
- [ ] Temporary files cleaned up on any error
- [ ] Database transaction rolled back on error (no orphaned records)
- [ ] One file failure doesn't prevent processing of others
- [ ] Enforces quota across entire batch before processing

**Estimated Effort**: 2-3 hours

---

## Step 3: Create Upload Model File

**File**: `app/models/uploads.py` (new)

**Rationale**: Move Upload model to dedicated file (one model per file convention). Keep legacy.py for reference only.

**Responsibilities**:
- Define Upload Tortoise ORM model mapped to existing `uploads` table
- Inherit TimestampMixin for auto-managed created_at/updated_at
- Use all existing fields as-is (no schema changes)

**Acceptance Criteria**:
- [ ] Upload model defined with all legacy fields (name, ext, originalname, cleanname, type, size, etc.)
- [ ] Model maps to existing `uploads` table
- [ ] TimestampMixin provides created_at/updated_at
- [ ] No database migration required (schema unchanged)
- [ ] Model passes Tortoise ORM validation

**Estimated Effort**: 30 minutes

---

## Step 4: Create Image Model File

**File**: `app/models/images.py` (new)

**Rationale**: Move Image model to dedicated file for clarity. Store image metadata extracted on upload.

**Responsibilities**:
- Define Image Tortoise ORM model mapped to existing `images` table
- Inherit TimestampMixin for created_at/updated_at
- Use all existing fields as-is (no schema changes)

**Acceptance Criteria**:
- [ ] Image model defined with all legacy fields (upload_id, type, width, height, bits, channels)
- [ ] Model maps to existing `images` table
- [ ] TimestampMixin provides created_at/updated_at
- [ ] No database migration required (schema unchanged)
- [ ] Model passes Tortoise ORM validation

**Estimated Effort**: 30 minutes

---

## Step 5: Update Model Imports

**File**: `app/models/__init__.py` (update)

**Tasks**:
- Import Upload from `app.models.uploads`
- Import Image from `app.models.images`
- Ensure legacy.py remains available for backward compatibility
- Verify Tortoise ORM discovers all models on initialization

**Acceptance Criteria**:
- [ ] Upload model importable from `app.models`
- [ ] Image model importable from `app.models`
- [ ] Legacy models still available for reference
- [ ] Tortoise ORM discovers and loads all models correctly

**Estimated Effort**: 15 minutes

---

## Step 6: Implement Image Metadata Extraction

**File**: `app/lib/image_processing.py` (new)

**Rationale**: Extract basic image metadata on upload (~50ms per image). Non-images skip this step.

**Responsibilities**:
- Extract dimensions (width, height) using Pillow
- Extract color depth (bits) and channels (RGB=3, RGBA=4)
- Validate MIME type via python-magic (already in deps)
- Handle errors gracefully (invalid image → error result, no crash)

**Acceptance Criteria**:
- [ ] Extracts image dimensions from file headers
- [ ] Extracts color depth and channel information
- [ ] Detects MIME type via python-magic
- [ ] Error handling doesn't crash on invalid images
- [ ] Metadata extraction completes in <100ms per typical image
- [ ] Non-image files skip processing (no error)

**Estimated Effort**: 1-2 hours

---

## Step 7: Implement API Upload Endpoint

**File**: `app/api/uploads.py` (new)

**Endpoint**: `POST /api/v1/uploads`

**Responsibilities**:
- Accept multipart/form-data with one or more files
- Require authenticated user (registered or unregistered)
- Delegate to UploadHandler for business logic
- Return JSON array of per-file results

**Acceptance Criteria**:
- [ ] Endpoint accessible at `POST /api/v1/uploads`
- [ ] Returns 401 if user not authenticated
- [ ] Returns 400 if no files provided
- [ ] Returns 200 with JSON array of UploadResult objects
- [ ] Each result includes success flag, file_id/error, filename, size
- [ ] Works with both registered and unregistered users

**Estimated Effort**: 1-2 hours

---

## Step 8: Implement UI Upload Endpoints

**File**: `app/ui/uploads.py` (new)

**Endpoints**:
- `GET /upload` → Display upload form page with widget
- `POST /upload` → Process form submission, redirect with flash messages

**Responsibilities**:
- Render upload form UI
- Process multipart form submission using UploadHandler
- Display flash messages for success/error counts
- Redirect to user profile or home

**Acceptance Criteria**:
- [ ] `GET /upload` returns upload form page with widget
- [ ] Form includes file input with multiple file support
- [ ] `POST /upload` processes multipart form data
- [ ] Returns 403 if user not authenticated
- [ ] Success/error flash messages displayed on redirect
- [ ] Reuses UploadHandler (same logic as API)

**Estimated Effort**: 1-2 hours

---

## Step 9: Build Upload Widget UI

**Files**:
- `app/ui/templates/uploads/form.html.j2` (main upload page)
- `app/ui/templates/uploads/widget.html.j2` (reusable component)

**Responsibilities**:
- Drag-and-drop file input
- Native OS file picker button
- Multiple file selection
- HTMX posting to `/upload` endpoint
- Alpine.js for real-time file list with status
- Display upload results (success/error per file)

**Acceptance Criteria**:
- [ ] Drag-and-drop file input functional
- [ ] File picker button opens native dialog
- [ ] Multiple file selection enabled
- [ ] HTMX posts to /upload endpoint
- [ ] Alpine.js displays file list with status (pending/success/error)
- [ ] Success/error messages styled and visible
- [ ] UI responsive at mobile breakpoints

**Estimated Effort**: 2-3 hours

---

## Step 10: Implement File Listing/Gallery

**File**: `app/ui/users.py` (extend existing profile page)

**Responsibilities**:
- Display user's uploaded files with metadata
- Query Upload table by user_id, ordered by date
- Show filename, upload date, file size for each
- Indicate if file is image (has Image record)
- Show placeholder/icon for each file type

**Acceptance Criteria**:
- [ ] Lists user's uploaded files in reverse chronological order
- [ ] Displays filename, date, size, file type
- [ ] Queries Image table to detect if file is image
- [ ] Shows placeholder for images (actual thumbnails Phase 2)
- [ ] Shows generic icon for non-image files
- [ ] Page requires authenticated user (403 if not)
- [ ] Template responsive at mobile breakpoints

**Estimated Effort**: 1-2 hours

---

## Step 11: Add Configuration for File Storage

**File**: `app/lib/config.py` (update)

**Responsibilities**:
- Add `files_dir` configuration (directory for uploaded files)
- Add `temp_file_retention_seconds` (TTL for temporary uploads)
- Validate configuration on load

**Note**: Existing config already includes all file size/type limits needed (user_max_file_size_mb, user_max_uploads, user_allowed_types, etc.)

**Acceptance Criteria**:
- [ ] `files_dir` config variable added with default "data/files"
- [ ] `temp_file_retention_seconds` config variable added with default 3600
- [ ] Configuration validates file_dir prevents directory traversal
- [ ] Invalid values raise descriptive errors on load
- [ ] `.env.example` updated with new variables

**Estimated Effort**: 30 minutes

---

## Step 12: Implement Temporary File Cleanup

**Integrated into UploadHandler** (Step 2):

**Responsibilities**:
- Save files to temp directory during processing
- Validate before committing to permanent storage
- Clean up temp files on any error
- Ensure no orphaned files or partial records

**Acceptance Criteria**:
- [ ] Temporary files created and cleaned up correctly
- [ ] Database rollback prevents orphaned records
- [ ] Concurrent uploads don't conflict (UUID uniqueness)
- [ ] Error scenarios properly cleaned up
- [ ] All-or-nothing per file (no partial uploads)

**Estimated Effort**: Integrated with Step 2

---

## Step 13: Create Tests for File Storage

**File**: `tests/test_lib_file_storage.py` (new)

**Acceptance Criteria**:
- [ ] Filename generation creates collision-proof names
- [ ] Filename generation includes date and UUID
- [ ] Filename generation handles special characters
- [ ] Path construction returns correct structure
- [ ] Quota checking enforces size limits
- [ ] Quota checking enforces count limits
- [ ] Path validation prevents directory traversal
- [ ] File save creates directories as needed
- [ ] File delete removes files correctly
- [ ] All tests pass

**Estimated Effort**: 2 hours

---

## Step 14: Create Tests for Upload Handler

**File**: `tests/test_lib_upload_handler.py` (new)

**Acceptance Criteria**:
- [ ] Single file upload succeeds
- [ ] Multiple file upload succeeds with partial failures
- [ ] Quota exceeded prevents upload
- [ ] Invalid MIME type rejected
- [ ] File validation errors returned in results
- [ ] Temporary files cleaned up on error
- [ ] Database rollback on error
- [ ] Image metadata extracted for images
- [ ] Image metadata not created for non-images
- [ ] Per-file errors don't cascade
- [ ] All tests pass

**Estimated Effort**: 2-3 hours

---

## Step 15: Create Tests for Upload Endpoints

**Files**:
- `tests/test_api_uploads.py` (new, API endpoint tests)
- `tests/test_ui_uploads.py` (new, UI endpoint tests)

**Acceptance Criteria**:
- [ ] POST /api/v1/uploads accepts and processes files
- [ ] POST /api/v1/uploads returns 401 if not authenticated
- [ ] POST /api/v1/uploads returns JSON array of results
- [ ] GET /upload returns upload form page
- [ ] POST /upload processes and redirects
- [ ] POST /upload returns 403 if not authenticated
- [ ] Both endpoints delegate to UploadHandler
- [ ] All tests pass

**Estimated Effort**: 2-3 hours

---

## Step 16: Create Tests for Models

**Files**:
- `tests/test_models_uploads.py` (new, Upload model tests)
- `tests/test_models_images.py` (new, Image model tests)

**Acceptance Criteria**:
- [ ] Upload model creation succeeds
- [ ] Upload model fields persist correctly
- [ ] Image model creation succeeds
- [ ] Image model fields persist correctly
- [ ] TimestampMixin manages created_at/updated_at
- [ ] Models map to existing tables
- [ ] No migration required
- [ ] All tests pass

**Estimated Effort**: 1-2 hours

---

## Step 17: Create Tests for Image Processing

**File**: `tests/test_lib_image_processing.py` (new)

**Acceptance Criteria**:
- [ ] Extract metadata from JPEG image
- [ ] Extract metadata from PNG image
- [ ] Extract metadata from GIF image
- [ ] Invalid image data handled gracefully
- [ ] Returned metadata has all required fields
- [ ] Color depth and channels detected correctly
- [ ] All tests pass

**Estimated Effort**: 1-2 hours

---

## Step 18: Manual Testing and Validation

**Tasks**:
- [ ] Test complete login → upload flow in browser
- [ ] Upload single file via UI
- [ ] Upload multiple files via UI
- [ ] Verify files stored in correct directory
- [ ] Verify Upload record created in database
- [ ] Verify Image record created for images
- [ ] Verify file metadata correct
- [ ] Test error handling (quota, invalid type)
- [ ] Verify flash messages displayed
- [ ] Test file listing shows uploaded files
- [ ] Test via API endpoint directly

**Acceptance Criteria**:
- [ ] Single and batch uploads work end-to-end
- [ ] Files stored in files_dir/{user_id}/{name}.{ext}
- [ ] Database records created correctly
- [ ] Image metadata extracted and stored
- [ ] Error messages clear and helpful
- [ ] File listing displays all user's uploads
- [ ] No security issues identified
- [ ] Performance acceptable for typical files

**Estimated Effort**: 2-3 hours

---

## Total Estimated Effort: ~25-35 hours

## References

- [Legacy Database Schema](./database-schema.md)
- [Feature Parity Requirements](./feature-parity.md)
- simplegallery implementation: `/Users/sam/code/simplegallery/app/lib/sifntupload/`
- HTMX file upload: https://htmx.org/examples/file-upload/
- Pillow documentation: https://pillow.readthedocs.io/
- Tortoise ORM models: https://tortoise.github.io/models.html
