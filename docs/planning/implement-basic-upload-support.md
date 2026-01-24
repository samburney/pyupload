# Implementation Plan: Core Upload Functionality (Phase 1)

## Overview

Implement sequential batch file upload with on-demand thumbnail caching, following simplegallery's proven patterns. Files are named using date + UUID format, stored by user ID in the filesystem, and metadata is tracked in the legacy `uploads` and `images` tables.

### Scope
- File receive and validation (MIME type, size, quotas)
- Sequential batch upload processing (Phase 1; parallel in Phase 2)
- File storage with user-organized directories
- Database record creation (Upload and Image models)
- Basic image metadata extraction (dimensions, color depth, channels)

### Current State
- ✅ Step 1: File storage abstraction layer (helpers, file_storage modules) — code complete, **tests missing**
- ✅ Step 2: Shared upload handler — code complete, **tests missing**
- ✅ Step 3: Upload model file — code complete, **tests missing**
- ✅ Step 4: Image model file — code complete, **tests missing**
- ✅ Step 5: Model imports updated — Upload and Image registered in MODEL_MODULES, **tests missing**
- ⏳ Step 6: Image metadata extraction — not started
- ⏳ Steps 7-18: Endpoints, UI, templates, and tests — not started

### Target State
- All 5 core infrastructure steps (Steps 1-5) have passing unit tests
- Image metadata extraction implemented (Step 6)
- API and UI upload endpoints fully functional (Steps 7-8)
- Upload widget UI with drag-and-drop and file listing (Steps 9-10)
- Configuration finalized and temporary file cleanup verified (Steps 11-12)
- Full test coverage for all infrastructure, endpoints, models, and image processing (Steps 13-17)
- End-to-end manual validation complete (Step 18)

**Note**: Per AGENTS.md guideline 6, unit tests are implicit acceptance criteria. Completed steps with missing tests must be treated as "code complete but acceptance criteria not yet validated."

---

## Out of Scope (Phase 2+)
- Archive extraction on upload (ZIP, TAR, TAR.GZ)
- Image thumbnail generation and caching
- Parallel batch processing
- Image watermarking
- EXIF data extraction

---

## Step 1: Create File Storage Abstraction Layer

**Status**: ✅ Code Complete | ⏳ Tests Required

**Files**: `app/lib/helpers.py`, `app/lib/file_storage.py`, `app/lib/config.py`

**Rationale**: Centralize file system operations, quota enforcement, and filename generation to avoid duplication across API and UI endpoints.

**Tasks**:
1. Implement filename generation with date + UUID format and collision resistance
2. Implement path construction using storage_path config and user_id
3. Implement quota validation (file size and upload count limits)
4. Implement filename sanitization for security (prevent directory traversal)
5. Implement file size detection for both UploadFile and BinaryIO objects
6. Configure storage_path, user_max_file_size_mb, user_max_uploads, user_allowed_types

**Tests**:
1. Filename generation creates collision-proof names with date + UUID
2. Filename generation includes date stamp (YYYYMMDD-HHMMSS) and 8-char UUID
3. Filename generation handles special characters via sanitization
4. Path construction returns correct user-specific directory structure
5. Quota checking enforces size limits correctly
6. Quota checking enforces upload count limits correctly
7. Path validation prevents directory traversal attacks
8. File size detection works for UploadFile objects
9. File size detection works for BinaryIO objects
10. Directory creation succeeds with proper permissions

**Acceptance Criteria**:
- [ ] Filename generation creates collision-proof names with date + UUID components
- [ ] Path construction uses storage_path config value and user_id
- [ ] Quota checking enforces user_max_file_size_mb and user_max_uploads limits
- [ ] File storage creates parent directories as needed
- [ ] Path validation prevents directory traversal attacks
- [ ] All functions have proper type hints and docstrings
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Implementation Notes**:
- `app/lib/helpers.py`: `make_unique_filename()`, `make_clean_filename()`, `split_filename()`, `validate_mime_types()`
- `app/lib/file_storage.py`: `make_upload_metadata()`, `get_file_size()`, `validate_user_quotas()`, user directory management
- Config values: `storage_path` (default `./data/uploads`), `user_max_file_size_mb`, `user_max_uploads`, `user_allowed_types`
- Multi-part extension support: `.tar.gz`, `.tar.bz2`, `.tar.xz`, `.tar.zstd`

**Estimated Effort**: ✅ Completed (code), 2 hours (testing)

---

## Step 2: Create Shared Upload Handler

**Status**: ✅ Code Complete | ⏳ Tests Required

**Files**: `app/lib/upload_handler.py`, `app/lib/file_storage.py`, `app/models/uploads.py`

**Rationale**: Centralize business logic for processing multiple files so both API and UI endpoints reuse identical logic, ensuring consistency and reducing duplication.

**Tasks**:
1. Implement single-file upload handler with validation and storage
2. Implement batch upload handler with per-file error recovery
3. Implement file validation (size, MIME type, quota enforcement)
4. Implement MIME type detection via python-magic
5. Implement database record creation (Upload model)
6. Implement automatic cleanup on errors (rollback file if DB record fails)
7. Implement UploadResult data structure for structured per-file responses

**Tests**:
1. Single file upload succeeds end-to-end
2. Batch file upload processes multiple files sequentially
3. Batch upload with partial failures: good files succeed, bad files fail
4. Quota exceeded prevents upload with appropriate error message
5. Invalid MIME type rejected with appropriate error message
6. File validation errors returned in per-file results (not cascade)
7. Temporary files cleaned up on validation error
8. Database cleanup prevents orphaned records (file deleted if DB record fails)
9. One file failure doesn't prevent processing of remaining files
10. UploadResult structure contains success/error status, file_id/message, filename, size
11. Empty file validation (no crash, proper error returned)
12. Supports unlimited quotas (max_file_size_mb=-1, max_uploads_count=-1)

**Acceptance Criteria**:
- [ ] Processes multiple files sequentially from list
- [ ] Validates each file independently (returns per-file results)
- [ ] Returns UploadResult array with success/error status
- [ ] Temporary files cleaned up on any error
- [ ] Database cleanup prevents orphaned records
- [ ] One file failure doesn't prevent processing of others
- [ ] Exception-based validation with specific error messages
- [ ] Supports unlimited quotas (-1 values)
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Implementation Notes**:
- `app/lib/upload_handler.py`: `handle_uploaded_file()`, `handle_uploaded_files()` with error recovery
- Custom exceptions: `UserQuotaExceeded`, `UserFileTypeNotAllowed` with descriptive messages
- Validation: `validate_user_filetypes()`, `validate_user_quotas()` in file_storage.py
- File operations: `make_upload_metadata()`, `add_uploaded_file()`, `save_uploaded_file()`
- MIME type detection via python-magic with empty file validation
- Multi-part extension support (`.tar.gz`, `.tar.bz2`, etc.)

**Dependencies**:
- Requires Step 1 (file storage abstraction layer) ✅ Complete
- Requires Upload model (Step 3) ✅ Complete
- Used by Step 7 (API endpoint) and Step 8 (UI endpoint)

**Estimated Effort**: ✅ Completed (code), 2-3 hours (testing)

---

## Step 3: Create Upload Model File

**Status**: ✅ Code Complete | ⏳ Tests Required

**Files**: `app/models/uploads.py`

**Rationale**: Move Upload model to dedicated file (one model per file convention). Keep legacy.py for reference only.

**Tasks**:
1. Define Upload Tortoise ORM model with all legacy fields
2. Inherit TimestampMixin for auto-managed created_at/updated_at
3. Map model to existing `uploads` table (no schema changes)
4. Define Pydantic UploadMetadata and UploadResult classes for API contracts
5. Register model in MODEL_MODULES for Tortoise ORM discovery

**Tests**:
1. Upload model creation succeeds
2. Upload model persists all required fields (name, ext, originalname, cleanname, type, size, etc.)
3. UploadMetadata Pydantic class validates filename pattern (date + UUID)
4. UploadMetadata validates MIME type format
5. UploadResult structure correctly indicates success/error
6. Model maps correctly to `uploads` table
7. TimestampMixin provides created_at/updated_at tracking
8. No database migration required (schema unchanged)

**Acceptance Criteria**:
- [ ] Upload model defined with all legacy fields
- [ ] Model maps to existing `uploads` table
- [ ] TimestampMixin provides created_at/updated_at
- [ ] No database migration required (schema unchanged)
- [ ] UploadMetadata validates filename format with date + UUID
- [ ] UploadResult structure complete for API responses
- [ ] Model passes Tortoise ORM validation
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Implementation Notes**:
- `app/models/uploads.py` contains: Upload model, UploadMetadata Pydantic class, UploadResult Pydantic class
- Fields: id, user_id, description, name, cleanname, originalname, ext, size, type, extra, viewed, private
- Validation patterns for filename (unique format with date + UUID), extension, MIME type
- created_at/updated_at managed by TimestampMixin

**Dependencies**:
- Requires Step 1 (file storage abstraction) ✅ Complete
- Used by Step 2 (upload handler) ✅ Complete

**Estimated Effort**: ✅ Completed (code), 1 hour (testing)

---

## Step 4: Create Image Model File

**Status**: ✅ Code Complete | ⏳ Tests Required

**Files**: `app/models/images.py`

**Rationale**: Move Image model to dedicated file for clarity. Store image metadata extracted on upload.

**Tasks**:
1. Define Image Tortoise ORM model with all legacy fields
2. Inherit TimestampMixin for auto-managed created_at/updated_at
3. Map model to existing `images` table (no schema changes)
4. Create relationship to Upload model (foreign key)
5. Register model in MODEL_MODULES for Tortoise ORM discovery

**Tests**:
1. Image model creation succeeds
2. Image model persists all required fields (upload_id, type, width, height, bits, channels)
3. Foreign key relationship to Upload model works correctly
4. Model maps correctly to `images` table
5. TimestampMixin provides created_at/updated_at tracking
6. No database migration required (schema unchanged)

**Acceptance Criteria**:
- [ ] Image model defined with all legacy fields (upload_id, type, width, height, bits, channels)
- [ ] Model maps to existing `images` table
- [ ] TimestampMixin provides created_at/updated_at
- [ ] Foreign key relationship to Upload model defined
- [ ] No database migration required (schema unchanged)
- [ ] Model passes Tortoise ORM validation
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Implementation Notes**:
- `app/models/images.py` contains: Image model with Upload foreign key
- Fields: id, upload (FK), type, width, height, bits, channels
- Relationship: Images have one Upload, Upload has many Images (one-to-many)
- created_at/updated_at managed by TimestampMixin

**Dependencies**:
- Requires Upload model (Step 3) ✅ Complete
- Used by Step 6 (image metadata extraction)

**Estimated Effort**: ✅ Completed (code), 1 hour (testing)

---

## Step 5: Update Model Imports

**Status**: ✅ Code Complete | ⏳ Tests Required

**Files**: `app/models/__init__.py`

**Rationale**: Ensure all models are registered in MODEL_MODULES so Tortoise ORM discovers them on initialization.

**Tasks**:
1. Import Upload from `app.models.uploads`
2. Import Image from `app.models.images`
3. Register both in MODEL_MODULES for Tortoise ORM discovery
4. Ensure legacy.py remains available for backward compatibility

**Tests**:
1. Upload model importable from `app.models`
2. Image model importable from `app.models`
3. Both models appear in MODEL_MODULES
4. Tortoise ORM discovers and loads all models correctly on init
5. Legacy models still available for reference

**Acceptance Criteria**:
- [ ] Upload model importable from `app.models` (registered in MODEL_MODULES)
- [ ] Image model importable from `app.models` (registered in MODEL_MODULES)
- [ ] Legacy models still available for reference/backward compatibility
- [ ] Tortoise ORM discovers and loads all models correctly
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Implementation Notes**:
- `app/models/__init__.py` registers both `app.models.uploads` and `app.models.images` in MODEL_MODULES
- Legacy models (from `app.models.legacy`) remain available
- Both Upload and Image models are Tortoise ORM models with TimestampMixin

**Dependencies**:
- Requires Upload model (Step 3) ✅ Complete
- Requires Image model (Step 4) ✅ Complete
- Used by Step 7 (API endpoint) and Step 8 (UI endpoint)

**Estimated Effort**: ✅ Completed (code), 30 minutes (testing)

---

## Step 6: Implement Image Metadata Extraction

**Status**: ⏳ Not Started

**Files**: `app/lib/image_processing.py` (new)

**Rationale**: Extract basic image metadata on upload (~50ms per image) to populate Image records. Non-images skip this step and return no error.

**Tasks**:
1. Create image_processing module with metadata extraction
2. Detect image MIME type via python-magic
3. Extract dimensions (width, height) using Pillow
4. Extract color depth (bits) and channels (RGB=3, RGBA=4)
5. Integrate extraction into upload handler flow
6. Implement graceful error handling (invalid image → error result, no crash)

**Tests**:
1. Extract metadata from JPEG image
2. Extract metadata from PNG image
3. Extract metadata from GIF image
4. Extract metadata from WebP image
5. Invalid image data handled gracefully
6. Returned metadata has all required fields (width, height, bits, channels)
7. Color depth and channels detected correctly
8. Non-image files skip processing (no error)
9. Corrupted files return error rather than crash
10. Metadata extraction completes in <100ms per typical image

**Acceptance Criteria**:
- [ ] Extracts image dimensions from file headers
- [ ] Extracts color depth and channel information
- [ ] Detects MIME type via python-magic
- [ ] Error handling doesn't crash on invalid images
- [ ] Metadata extraction completes in <100ms per typical image
- [ ] Non-image files skip processing (no error)
- [ ] Integration with upload handler complete
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Implementation Notes**:
- Module should provide: `extract_image_metadata(file: BinaryIO) -> ImageMetadata | None`
- Dependencies: Pillow (PIL), python-magic (already in project deps)
- Return None for non-images or errors (handled gracefully)
- Performance target: <100ms per 2MB image on typical hardware

**Dependencies**:
- Requires Image model (Step 4) ✅ Complete
- Used by Step 2 (upload handler) - integration needed
- Impacts Step 14 testing (image metadata in results)

**Estimated Effort**: 1-2 hours

---

## Step 7: Implement API Upload Endpoint

**Status**: ⏳ Not Started

**Files**: `app/api/uploads.py` (new)

**Endpoint**: `POST /api/v1/uploads`

**Rationale**: Provide REST API endpoint for programmatic file uploads with JSON response.

**Tasks**:
1. Create uploads.py in app/api
2. Implement POST /api/v1/uploads endpoint accepting multipart/form-data
3. Require authenticated user (registered or unregistered)
4. Delegate to UploadHandler for business logic
5. Return JSON array of per-file results (UploadResult objects)
6. Implement 401 error if user not authenticated
7. Implement 400 error if no files provided

**Tests**:
1. Endpoint accessible at POST /api/v1/uploads
2. Returns 401 if user not authenticated
3. Returns 400 if no files provided
4. Returns 200 with JSON array of UploadResult objects
5. Single file upload returns array with one result
6. Batch file upload returns array with multiple results
7. Each result includes success flag, file_id or error, filename, size
8. Works with registered users (with JWT)
9. Works with unregistered users (with fingerprint auth)
10. Errors in one file don't affect others

**Acceptance Criteria**:
- [ ] Endpoint accessible at `POST /api/v1/uploads`
- [ ] Returns 401 if user not authenticated
- [ ] Returns 400 if no files provided
- [ ] Returns 200 with JSON array of UploadResult objects
- [ ] Each result includes success flag, file_id/error, filename, size
- [ ] Works with both registered and unregistered users
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Dependencies**:
- Requires Steps 1-5 (infrastructure) ✅ Complete
- Requires Step 2 (upload handler) ✅ Complete
- Used by Step 15 (API endpoint tests)

**Estimated Effort**: 1-2 hours

---

## Step 8: Implement UI Upload Endpoints

**Status**: ⏳ Not Started

**Files**: `app/ui/uploads.py` (new)

**Endpoints**:
- `GET /upload` → Display upload form page with widget
- `POST /upload` → Process form submission, redirect with flash messages

**Rationale**: Provide traditional form-based upload for browser users with server-side processing.

**Tasks**:
1. Create uploads.py in app/ui
2. Implement GET /upload endpoint returning HTML form page
3. Implement POST /upload endpoint accepting multipart form data
4. Delegate to UploadHandler for business logic
5. Display flash messages for success/error counts
6. Redirect to user profile or home page after upload
7. Implement 403 error if user not authenticated

**Tests**:
1. GET /upload returns upload form page with HTML
2. GET /upload returns 403 if user not authenticated
3. Form includes file input with multiple file support
4. POST /upload processes multipart form data
5. POST /upload returns 403 if user not authenticated
6. Success flash message displayed on redirect
7. Error flash message displayed on redirect
8. Per-file errors shown in flash messages
9. Both endpoints delegate to same UploadHandler
10. Partial upload failures show correct error counts

**Acceptance Criteria**:
- [ ] `GET /upload` returns upload form page with widget
- [ ] Form includes file input with multiple file support
- [ ] `POST /upload` processes multipart form data
- [ ] Returns 403 if user not authenticated
- [ ] Success/error flash messages displayed on redirect
- [ ] Reuses UploadHandler (same logic as API)
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Dependencies**:
- Requires Steps 1-5 (infrastructure) ✅ Complete
- Requires Step 2 (upload handler) ✅ Complete
- Used by Step 15 (UI endpoint tests)

**Estimated Effort**: 1-2 hours

---

## Step 9: Build Upload Widget UI

**Status**: ⏳ Not Started

**Files**: 
- `app/ui/templates/uploads/form.html.j2` (main upload page)
- `app/ui/templates/uploads/widget.html.j2` (reusable component)

**Rationale**: Create interactive UI with drag-and-drop, file preview, and progress feedback using HTMX + Alpine.js.

**Tasks**:
1. Create upload form template (main page)
2. Create upload widget component (reusable across pages)
3. Implement drag-and-drop file input area
4. Implement native OS file picker button
5. Implement multiple file selection support
6. Implement HTMX integration for posting to /upload endpoint
7. Implement Alpine.js for client-side file list and status
8. Implement real-time status display (pending/success/error per file)
9. Style upload results (success/error messages)
10. Ensure responsive design at mobile breakpoints

**Tests**:
1. Drag-and-drop file input functional
2. File picker button opens native dialog
3. Multiple file selection works
4. HTMX posts to /upload endpoint
5. Alpine.js displays file list
6. Status updates on response (success/error)
7. Error messages visible and readable
8. Success messages visible and readable
9. UI responsive at mobile (375px) breakpoints
10. UI responsive at tablet (768px) breakpoints
11. UI responsive at desktop (1024px+) breakpoints

**Acceptance Criteria**:
- [ ] Drag-and-drop file input functional
- [ ] File picker button opens native dialog
- [ ] Multiple file selection enabled
- [ ] HTMX posts to /upload endpoint
- [ ] Alpine.js displays file list with status (pending/success/error)
- [ ] Success/error messages styled and visible
- [ ] UI responsive at mobile breakpoints
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Dependencies**:
- Requires Step 8 (UI endpoint /upload) ⏳ Not started
- Uses HTMX (already in project deps)
- Uses Alpine.js (already in project deps)

**Estimated Effort**: 2-3 hours

---

## Step 10: Implement File Listing/Gallery

**Status**: ⏳ Not Started

**Files**: `app/ui/users.py` (extend existing profile page)

**Rationale**: Display user's uploaded files with metadata in a gallery view on profile page.

**Tasks**:
1. Extend user profile page with file listing section
2. Query Upload table by user_id, ordered by date descending
3. For each upload, retrieve associated Image record (if exists)
4. Display filename, upload date, file size, file type
5. Show image placeholder if upload has Image record
6. Show generic icon for non-image files
7. Implement pagination or lazy loading for large file counts
8. Ensure responsive gallery layout at mobile breakpoints

**Tests**:
1. Lists user's uploaded files in reverse chronological order
2. Displays filename, date, size, file type correctly
3. Queries Image table to detect if file is image
4. Shows placeholder for images (actual thumbnails in Phase 2)
5. Shows generic icon for non-image files
6. Page requires authenticated user (403 if not)
7. Pagination or lazy loading works with 100+ files
8. Gallery layout responsive at mobile breakpoints
9. Gallery layout responsive at tablet breakpoints
10. Gallery layout responsive at desktop breakpoints

**Acceptance Criteria**:
- [ ] Lists user's uploaded files in reverse chronological order
- [ ] Displays filename, date, size, file type
- [ ] Queries Image table to detect if file is image
- [ ] Shows placeholder for images (actual thumbnails Phase 2)
- [ ] Shows generic icon for non-image files
- [ ] Page requires authenticated user (403 if not)
- [ ] Template responsive at mobile breakpoints
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Dependencies**:
- Requires Upload model (Step 3) ✅ Complete
- Requires Image model (Step 4) ✅ Complete
- Impacts Step 10 (file testing) - verify gallery displays uploads

**Estimated Effort**: 1-2 hours

---

## Step 11: Add Configuration for File Storage

**Status**: ⏳ Not Started

**Files**: `app/lib/config.py` (update)

**Rationale**: Centralize file storage configuration and validate on startup.

**Tasks**:
1. Add `files_dir` configuration variable (default "data/files")
2. Add `temp_file_retention_seconds` configuration variable (default 3600)
3. Add configuration validation to prevent directory traversal
4. Add descriptive error messages for invalid config values
5. Update `.env.example` with new configuration variables

**Tests**:
1. `files_dir` config variable added and readable
2. `files_dir` has sensible default
3. `temp_file_retention_seconds` config variable added and readable
4. `temp_file_retention_seconds` has sensible default
5. Configuration validates files_dir prevents directory traversal
6. Invalid files_dir path raises descriptive error
7. Invalid retention TTL raises descriptive error
8. `.env.example` includes new variables with documentation

**Acceptance Criteria**:
- [ ] `files_dir` config variable added with default "data/files"
- [ ] `temp_file_retention_seconds` config variable added with default 3600
- [ ] Configuration validates file_dir prevents directory traversal
- [ ] Invalid values raise descriptive errors on load
- [ ] `.env.example` updated with new variables
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Dependencies**:
- Requires Step 11 (config updates already in place?) - verify existing config structure

**Estimated Effort**: 30 minutes

---

## Step 12: Implement Temporary File Cleanup

**Status**: ✅ Integrated into Step 2 | ⏳ Tests Required

**Files**: Part of `app/lib/upload_handler.py`, `app/lib/file_storage.py`

**Rationale**: Ensure no orphaned or partial files remain when uploads fail.

**Tasks**:
1. Files are saved to user directory during processing (in Step 2)
2. Validation occurs before database record creation
3. On validation error, file is cleaned up immediately
4. On database error, file is deleted and DB transaction rolled back
5. Concurrent uploads prevented conflicts via UUID uniqueness
6. All error scenarios result in complete cleanup (all-or-nothing per file)

**Tests**:
1. Temporary files created during processing
2. Temporary files cleaned up on validation error
3. Temporary files cleaned up on database record failure
4. Database rollback prevents orphaned records
5. File deletion succeeds even if DB record creation fails
6. Concurrent uploads don't conflict (UUID uniqueness)
7. Error scenarios properly cleaned up (no orphaned files)
8. All-or-nothing per file (no partial uploads)
9. Multiple concurrent uploads each cleaned up correctly
10. File I/O errors don't prevent database cleanup

**Acceptance Criteria**:
- [ ] Temporary files created and cleaned up correctly
- [ ] Database rollback prevents orphaned records
- [ ] File deletion on DB error prevents partial uploads
- [ ] Concurrent uploads don't conflict (UUID uniqueness)
- [ ] Error scenarios properly cleaned up
- [ ] All-or-nothing per file (no partial uploads)
- [ ] Unit tests written and passing (implicit acceptance criteria per AGENTS.md)

**Implementation Notes**:
- Implemented in Step 2 as part of upload handler
- File saved directly to user directory (no temp directory needed - UUID ensures uniqueness)
- Cleanup occurs in exception handlers in upload handler
- Database errors trigger file deletion via cleanup code

**Dependencies**:
- Requires Step 1 (file storage) ✅ Complete
- Requires Step 2 (upload handler) ✅ Complete

**Estimated Effort**: Integrated with Step 2 (code), 1 hour (testing)

---

## Step 13: Manual Testing and Validation

**Status**: ⏳ Not Started

**Acceptance Criteria – Core Functionality**:
- [ ] Complete login → upload flow works end-to-end
- [ ] Single file upload via UI succeeds
- [ ] Batch file upload via UI succeeds
- [ ] Files stored in correct user directory
- [ ] Upload records created in database
- [ ] Image records created for image files
- [ ] File metadata correct (size, type, timestamp)
- [ ] File listing shows uploaded files

**Acceptance Criteria – Error Handling**:
- [ ] Quota exceeded shows error message
- [ ] Invalid file type shows error message
- [ ] File too large shows error message
- [ ] Error on one file doesn't affect others
- [ ] Flash messages clear and helpful

**Acceptance Criteria – Security**:
- [ ] No path traversal exploits
- [ ] No access to others' files
- [ ] Filenames sanitized correctly
- [ ] Quotas enforced per user

**Acceptance Criteria – Performance**:
- [ ] Single file upload completes <5 seconds
- [ ] Batch upload (10 files, 1MB each) completes <30 seconds
- [ ] Image metadata extraction <100ms per image
- [ ] UI responsive and not blocked during upload

**Estimated Effort**: 2-3 hours

---

## Summary

### Implementation Progress
- **Complete (Code)**: Steps 1-5 (infrastructure complete but tests required)
- **Not Started**: Steps 6-12 (image processing, endpoints, UI, configuration, cleanup)
- **Pending**: Step 13 (manual testing and validation)

### Critical Note: Test Requirements
Per AGENTS.md guideline 6: "Unit tests must be implemented as each task progresses. Adequate tests written and passing are considered an implicit acceptance criteria."

**Steps 1-5 are code-complete but CANNOT be marked as fully accepted until tests are written and passing** for each step. Test requirements for each implementation step are embedded in the step's **Tests** section.

### Effort Breakdown

| Phase | Steps | Status | Estimated Effort |
|-------|-------|--------|------------------|
| Infrastructure | 1-5 | Code Complete | 6 hrs tests required |
| Image Processing | 6 | Not Started | 2 hrs code + 1 hr tests |
| API & UI Endpoints | 7-8 | Not Started | 2 hrs code + 2 hrs tests each |
| Upload UI & Config | 9-12 | Not Started | 5 hrs code + 2 hrs tests |
| Manual Validation | 13 | Not Started | 3 hrs |
| **Total** | 1-13 | **38% complete** | **~24 hours remaining** |

---

## References

- [Legacy Database Schema](./database-schema.md)
- [Feature Parity Requirements](./feature-parity.md)
- simplegallery upload implementation: `/Users/sam/code/simplegallery/app/lib/sifntupload/`
- HTMX file upload: https://htmx.org/examples/file-upload/
- Pillow documentation: https://pillow.readthedocs.io/
- Tortoise ORM models: https://tortoise.github.io/models.html
- AGENTS.md: Guidelines for LLM contributions to this project
