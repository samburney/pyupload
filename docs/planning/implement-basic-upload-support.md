# Core Upload Functionality Implementation Plan (Phase 1)

## Overview

Implement sequential batch file upload with on-demand thumbnail caching, following simplegallery's proven patterns. Files are named using date + UUID format, stored by user ID in the filesystem, and metadata is tracked in the legacy `uploads` and `images` tables.

**Scope**: File receive, validation, storage, and basic image metadata extraction (Phase 1).  
**Out of Scope**: Archive extraction, image thumbnail generation/caching, parallel batch processing, watermarking, EXIF extraction.

---

## Step 1: Create File Storage Abstraction Layer ✅ COMPLETED

**Files**: `app/lib/helpers.py`, `app/lib/file_storage.py`, `app/lib/config.py`

**Rationale**: Centralize file system operations, quota enforcement, and filename generation to avoid duplication across API and UI endpoints.

**Responsibilities**:
- Generate collision-free filenames using date + UUID format (`description_YYYYMMDD-HHMMSS-UUUUUUUU`): ✅ DONE
- Validate filename/path for security (prevent path traversal): ✅ DONE - filenames are sanitised via `clean_filename()`
- Construct config-driven file paths (storage_path from AppConfig): ✅ DONE
- Enforce user quotas (max file size, max upload count): ✅ DONE
- Manage filesystem operations (create directories, save/delete files):
    - File upload parent path and user paths: ✅ DONE via `user_filepath()`
    - Save: Deferred to Step 2 upload handler
    - Delete: Future feature (not in scope)

**Acceptance Criteria**:
- [x] Filename generation creates collision-proof names with date + UUID components
- [x] Path construction uses storage_path config value and user_id
- [x] Quota checking enforces user_max_file_size_mb and user_max_uploads limits
- [x] File storage creates parent directories as needed
- [x] Path validation prevents directory traversal attacks (via `clean_filename()`)
- [x] All functions have proper type hints and docstrings

**Actual Implementation Details**:

**`app/lib/helpers.py`** provides utility functions:
- `unique_filename()`: Generates `{clean_name}_{YYYYMMDD-HHMMSS}_{UUID_8chars}.{ext}` format (collision-resistant)
- `clean_filename()`: Removes unsafe characters, prevents directory traversal via alphanumeric/dash/underscore/dot filtering
- `split_filename()`: Separates name and extension
- `validate_mime_types()`: RFC 6838 MIME type validation for config values

**`app/lib/file_storage.py`** provides file operations:
- `user_filepath()`: Generates `{storage_path}/user_{user_id}/{unique_filename}`, creates user directory
- `get_file_size()`: Gets file size in bytes, handles both UploadFile and BinaryIO
- `validate_user_quotas()`: Checks file size and upload count against user limits

**`app/lib/config.py`** provides configuration:
- `storage_path`: Configurable via `STORAGE_PATH` env var (default `./data/uploads`), auto-created
- `user_max_file_size_mb`: Configurable per-user file size limit
- `user_max_uploads`: Configurable per-user upload count (-1 for unlimited)
- `user_allowed_types`: Configurable MIME types allowed
- Similar limits for unregistered users

**Status Notes**:
- Step 1 is **feature-complete** and ready for use by subsequent steps
- No tests yet created (Step 13)
- File save/delete operations deferred to handler layer (Step 2)

**Estimated Effort**: ✅ Completed

---

## Step 2: Create Shared Upload Handler ✅ COMPLETED

**Files**: `app/lib/upload_handler.py` ✅ DONE, `app/lib/file_storage.py` ✅ DONE, `app/models/uploads.py` ✅ DONE

**Rationale**: Centralize business logic for processing multiple files so both API and UI endpoints reuse identical logic.

**Responsibilities**:
- Process multiple files sequentially (Phase 1): ✅ DONE
- Validate each file before storage (size, type, security): ✅ DONE
- Enforce quotas per file: ✅ DONE
- Handle per-file errors without cascading: ✅ DONE
- Manage temporary file cleanup on errors: ✅ DONE
- Create Upload and Image records in database
    - Upload record: ✅ DONE
    - Image record: DEFERRED (out of scope, Phase 2)

**Implementation Status** (COMPLETE):

**What's Implemented**:
- ✅ `handle_uploaded_file(user, file)` → single file handler with validation and storage
- ✅ `handle_uploaded_files(user, files)` → batch handler with per-file error recovery
- ✅ Custom exceptions: `UserQuotaExceeded`, `UserFileTypeNotAllowed` with descriptive messages
- ✅ Validation layer: `validate_user_filetypes()`, `validate_user_quotas()` with proper error handling
- ✅ File operations: `make_upload_metadata()`, `add_uploaded_file()`, `save_uploaded_file()`, `record_uploaded_file()`
- ✅ MIME type detection via python-magic with empty file validation
- ✅ File size calculation and quota enforcement with unlimited (-1) support
- ✅ Database record creation with automatic cleanup on errors (file deleted if DB record fails)
- ✅ UploadResult data structure for structured per-file responses
- ✅ Multi-part extension support (`.tar.gz`, `.tar.bz2`, etc.)
- ✅ Filename sanitization with case normalization
- ✅ Proper file pointer management for both UploadFile and BinaryIO

**Acceptance Criteria**:
- [x] Processes multiple files sequentially from list
- [x] Validates each file independently (returns per-file results)
- [x] Returns UploadResult array with success/error status
- [x] Temporary files cleaned up on any error
- [x] Database cleanup prevents orphaned records (file deleted if record creation fails)
- [x] One file failure doesn't prevent processing of others
- [x] Exception-based validation with specific error messages
- [x] Supports unlimited quotas (max_file_size_mb=-1, max_uploads_count=-1)

**Ready for**: API endpoint (Step 7) and UI endpoint (Step 8) implementation

**Estimated Effort**: ✅ Completed

---

## Step 3: Create Upload Model File ✅ COMPLETED

**File**: `app/models/uploads.py` ✅ DONE

**Rationale**: Move Upload model to dedicated file (one model per file convention). Keep legacy.py for reference only.

**Responsibilities**:
- Define Upload Tortoise ORM model mapped to existing `uploads` table: ✅ DONE
- Inherit TimestampMixin for auto-managed created_at/updated_at: ✅ DONE
- Use all existing fields as-is (no schema changes): ✅ DONE

**Acceptance Criteria**:
- [x] Upload model defined with all legacy fields (name, ext, originalname, cleanname, type, size, etc.)
- [x] Model maps to existing `uploads` table
- [x] TimestampMixin provides created_at/updated_at
- [x] No database migration required (schema unchanged)
- [x] Model passes Tortoise ORM validation

**Status**: Model file includes supporting Pydantic classes `UploadMetadata` and `UploadResult` created during Step 2. Already registered in `MODEL_MODULES` for Tortoise ORM discovery.

**Estimated Effort**: ✅ Completed

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

## Step 5: Update Model Imports ✅ PARTIALLY COMPLETED

**File**: `app/models/__init__.py` (update)

**Tasks**:
- Import Upload from `app.models.uploads`: ✅ DONE
- Import Image from `app.models.images`: ⏳ PENDING (Step 4)
- Ensure legacy.py remains available for backward compatibility: ✅ DONE
- Verify Tortoise ORM discovers all models on initialization: ✅ DONE

**Acceptance Criteria**:
- [x] Upload model importable from `app.models` (registered in MODEL_MODULES)
- [ ] Image model importable from `app.models` (pending Step 4)
- [x] Legacy models still available for reference
- [x] Tortoise ORM discovers and loads all models correctly

**Status**: Upload and legacy modules already in `MODEL_MODULES`. Will add Image module once Step 4 is complete.

**Estimated Effort**: ✅ Partial (Upload done, Image pending)

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
