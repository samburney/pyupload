# Implementation Plan: File Serving Endpoint

## Implementation Progress

**Status**: Steps 1-3 Complete ✅ | Step 4 Partial ⚠️ | Steps 5-6 Pending

**Completed**:
- ✅ Step 1: File serving endpoints (UI complete, API pending)
- ✅ Step 2: Access control (private/public files)
- ✅ Step 3: View counter (increments for non-owners)
- ⚠️ Step 4: Content-Type and headers (basic implementation, advanced features pending)

**Pending**:
- ⏳ Step 1: API endpoint implementation
- ⏳ Step 4: Advanced headers (ETag, Last-Modified, conditional requests)
- ⏳ Step 5: Remove temporary static route
- ⏳ Step 6: Integration testing and security review

**Last Updated**: 2026-02-01

---

## Overview

Implement a secure file serving endpoint that replaces the temporary static file route, provides proper access control for private files, increments view counters, and serves files with appropriate MIME types and headers.

### Scope
- File serving endpoint at `/get/{id}/{filename}`
- Access control enforcement (private files owner-only, public files accessible to all)
- View counter increment on successful file delivery
- Proper MIME type detection and headers
- Support for both direct file downloads and inline viewing
- Error handling for missing files, unauthorized access
- Remove temporary `/files/` static route

### Current State
- Files are stored in `data/files/user_{id}/` directories
- Upload model has `url` property that generates `/get/{id}/{filename}` URLs
- Upload model has `static_url` property pointing to `/files/` (temporary)
- Temporary static file route mounted at `/files/` in `app/main.py`
- Upload model has `private` field (0 or 1) but not enforced
- Upload model has `viewed` field but never incremented
- No file serving endpoint implemented

### Target State
- Secure `/get/{id}/{filename}` endpoint serving files
- Private files (private=1) only accessible to file owner
- Public files (private=0) accessible to all users (authenticated or anonymous)
- View counter incremented on each successful file delivery
- Proper Content-Type headers based on file MIME type
- Content-Disposition header for downloads vs inline viewing
- 404 errors for non-existent files
- 403 errors for unauthorized access to private files
- Temporary `/files/` static route removed
- All tests passing with new functionality

---

## Step 1: Create File Serving Endpoints

**Files**: 
- `app/ui/uploads.py` (modified - added file serving endpoints)
- `app/api/files.py` (new - pending)
- `app/lib/file_serving.py` (new - ✅ created)
- `app/lib/helpers.py` (modified - added `sanitise_filename`)
- `app/main.py` (modified - added query param handling)

**Tasks**:
1. [x] Create file serving logic in `app/lib/file_serving.py`
2. [x] Implement UI endpoint GET `/get/{id}/{filename}` (optional filename)
3. [ ] Implement API endpoint GET `/api/v1/files/{id}` (returns JSON metadata + download URL)
4. [x] Validate upload ID exists in database
5. [x] Use filename from URL if provided, otherwise use `Upload.filename`
6. [x] Sanitize filename to prevent injection attacks (added `sanitise_filename` function)
7. [x] Check file exists on filesystem using `Upload.filepath`
8. [x] Return FileResponse with appropriate headers
9. [x] Handle errors (404 for missing files, 403 for unauthorized, 500 for unexpected)
10. [x] Register endpoints in uploads router

**Tests**:
1. [x] Test successful file serving for existing upload
2. [x] Test serving with custom filename in URL
3. [x] Test serving without filename (redirects to SEO-friendly URL)
4. [x] Test 404 for non-existent upload ID
5. [x] Test 404 for missing file on filesystem
6. [x] Test filename sanitization prevents injection (18 comprehensive tests)
7. [ ] Test both UI and API endpoints work identically

**Acceptance Criteria**:
- [x] UI endpoint serves files successfully
- [ ] API endpoint serves files successfully
- [x] Filename can be customized in URL for SEO
- [x] Redirect to SEO-friendly URL when filename omitted
- [x] Proper error handling for all failure cases
- [x] All tests passing (16 file serving tests + 18 sanitization tests)

**Implementation Notes**:
- UI endpoint returns HTML error pages on failure
- API endpoint returns JSON error responses on failure
- Both call common function in `app/lib/file_serving.py`
- Filename is identified by `id` only; URL filename is cosmetic/SEO
- Sanitize filename: remove path separators, null bytes, control characters
- Use `Upload.filepath` property to get correct file path
- Use `mimetypes.guess_type()` for MIME type detection
- Default to `application/octet-stream` if MIME type unknown

---

## Step 2: Implement Access Control

**Files**: 
- `app/lib/file_serving.py` (✅ implemented)
- `app/ui/uploads.py` (✅ integrated)

**Tasks**:
1. [x] Get current user from request (authenticated or anonymous)
2. [x] Check if upload is private (private=1)
3. [x] If private, verify current user is the owner
4. [x] Return 403 Forbidden if unauthorized (raises `NotAuthorisedError`)
5. [x] Allow access if public or user is owner
6. [x] Handle edge cases (None user for anonymous access)

**Tests**:
1. [x] Test public file accessible to anonymous users
2. [x] Test public file accessible to authenticated users (via owner test)
3. [x] Test private file accessible to owner
4. [x] Test private file returns 403 for other authenticated users
5. [x] Test private file returns 403 for anonymous users

**Acceptance Criteria**:
- [x] Private files only accessible to owners
- [x] Public files accessible to all
- [x] Proper 403 errors for unauthorized access (raises `NotAuthorisedError`)
- [x] All access control tests passing

**Implementation Notes**:
- Use `get_current_user_from_request()` to get user (returns None for anonymous)
- Compare `upload.user_id` with `current_user.id`
- Admin access to all files is out of scope (future enhancement)

**Dependencies**:
- Step 1 must be complete

---

## Step 3: Implement View Counter

**Files**: 
- `app/lib/file_serving.py` (✅ implemented)

**Tasks**:
1. [x] Increment `viewed` field on successful file delivery
2. [x] Use simple increment (atomic updates via Tortoise ORM)
3. [x] Only increment for successful responses (not 404/403)
4. [x] Do NOT increment when owner views their own file
5. [x] Handle database errors gracefully (within transaction)

**Tests**:
1. [x] Test view counter increments on file access by non-owner
2. [x] Test view counter increments for anonymous users (same as #1)
3. [x] Test view counter does NOT increment for owner views
4. [x] Test view counter doesn't increment on 404 (error raised before increment)
5. [x] Test view counter doesn't increment on 403 (error raised before increment)
6. [ ] Test atomic increment (concurrent requests) - **DEFERRED** (Tortoise ORM handles)
7. [ ] Test view counter visible in upload metadata - **COVERED BY EXISTING TESTS**

**Acceptance Criteria**:
- [x] View counter increments on each successful file delivery by non-owners
- [x] Owner views do not increment counter
- [x] Counter uses ORM save (thread-safe via database)
- [x] No increment on error responses
- [x] All tests passing

**Implementation Notes**:
- Use Tortoise ORM's `F()` expression for atomic increment: `upload.viewed = F('viewed') + 1`
- Check if `current_user.id != upload.user_id` before incrementing
- Increment after access control check but before FileResponse
- Consider logging view events for analytics

**Dependencies**:
- Step 1 must be complete
- Step 2 must be complete

---

## Step 4: Content-Type and Headers

**Status**: ⚠️ Partially Complete (Basic headers implemented, advanced features pending)

**Files**: 
- `app/lib/file_serving.py` (✅ basic implementation)

**Tasks**:
1. [x] Detect MIME type from file extension (using Upload.type field)
2. [x] Set Content-Type header appropriately
3. [x] Set Content-Disposition header based on file type and download parameter
4. [x] Support `?download=1` query parameter to force download
5. [x] Default to inline for browser-renderable types (images, videos, audio, PDF, text/plain)
6. [x] Default to attachment for non-renderable types
7. [x] Set cache headers (1 hour, private for private files, public for public)
8. [ ] Add Last-Modified header based on upload timestamp
9. [ ] Generate and set ETag header based on upload metadata
10. [ ] Support conditional requests with If-Modified-Since
11. [ ] Support conditional requests with If-None-Match (ETag validation)

**Tests**:
1. [ ] Test correct MIME type for images
2. [ ] Test correct MIME type for videos
3. [ ] Test correct MIME type for audio
4. [ ] Test correct MIME type for PDF
5. [ ] Test correct MIME type for documents
6. [ ] Test Content-Disposition inline for images (no download param)
7. [ ] Test Content-Disposition inline for videos (no download param)
8. [ ] Test Content-Disposition attachment for binary files
9. [ ] Test Content-Disposition attachment with ?download=1 for all types
10. [ ] Test Cache-Control private for private files
11. [ ] Test Cache-Control public for public files
12. [ ] Test Last-Modified header present
13. [ ] Test ETag header present
14. [ ] Test 304 Not Modified with If-Modified-Since
15. [ ] Test 304 Not Modified with If-None-Match (ETag)
16. [ ] Test ETag changes when upload metadata changes

**Acceptance Criteria**:
- [ ] Correct MIME types for all file types
- [ ] Browser-renderable files display inline by default
- [ ] Non-renderable files download by default
- [ ] ?download=1 forces download for all file types
- [ ] Appropriate cache headers set (public/private, 1 hour)
- [ ] Conditional requests supported (both Last-Modified and ETag)
- [ ] ETags invalidate when upload changes
- [ ] All tests passing

**Implementation Notes**:
- Use Python's `mimetypes` module for MIME type detection
- Browser-renderable types (safe for inline display):
  - `image/*` (all images including SVG)
  - `video/*` (all video formats)
  - `audio/*` (all audio formats)
  - `application/pdf`
  - `text/plain` (safe for logs, readme files, etc.)
- Force download for security/UX reasons:
  - `text/html` - XSS risk
  - `text/javascript`, `application/javascript` - XSS risk
  - `text/css` - CSS injection risk
  - `application/json`, `text/xml`, `application/xml` - Better as downloads
  - All other types - download by default
- Content-Disposition inline: `inline; filename="{filename}"`
- Content-Disposition attachment: `attachment; filename="{filename}"`
- Cache-Control for private files: `private, max-age=3600` (1 hour)
- Cache-Control for public files: `public, max-age=3600` (1 hour)
- Last-Modified: Use `upload.updated_at` or `upload.created_at`
- ETag generation: `hashlib.md5(f"{upload.id}-{upload.updated_at}".encode()).hexdigest()`
- Return 304 if file not modified since If-Modified-Since header
- Return 304 if ETag matches If-None-Match header
- ETag should be quoted: `ETag: "abc123"`

**Dependencies**:
- Step 1 must be complete

---

## Step 5: Remove Temporary Static Route

**Files**: 
- `app/main.py`
- `app/models/uploads.py`

**Tasks**:
1. [ ] Remove `/files/` static mount from main.py
2. [ ] Remove `static_url` property from Upload model (or mark deprecated)
3. [ ] Update any templates using `static_url` to use `url` instead
4. [ ] Update tests that rely on static file serving
5. [ ] Verify all upload links work with new endpoint

**Tests**:
1. [ ] Test `/files/` route no longer accessible
2. [ ] Test all upload URLs use `/get/` endpoint
3. [ ] Test profile page displays uploads correctly
4. [ ] Test upload list page works

**Acceptance Criteria**:
- [ ] `/files/` static route removed
- [ ] All file access goes through `/get/` endpoint
- [ ] No broken links in UI
- [ ] All tests passing

**Implementation Notes**:
- Search codebase for references to `/files/` or `static_url`
- Update templates to use `upload.url` instead of `upload.static_url`
- This is the final cleanup step

**Dependencies**:
- Steps 1-4 must be complete
- All functionality must be working through new endpoint

---

## Step 6: Integration Testing and Security Review

**Files**: 
- `tests/` (various test files)

**Tasks**:
1. [ ] Create comprehensive integration tests
2. [ ] Test all file types (images, videos, documents)
3. [ ] Test edge cases (large files, special characters in filenames)
4. [ ] Security review for path traversal vulnerabilities
5. [ ] Security review for access control bypasses
6. [ ] Performance testing for concurrent requests
7. [ ] Update documentation

**Tests**:
1. [ ] Integration test: Upload → View → Download workflow
2. [ ] Integration test: Private file access control
3. [ ] Security test: Path traversal attempts
4. [ ] Security test: Access control bypass attempts
5. [ ] Performance test: Concurrent file serving
6. [ ] Load test: Large file serving

**Acceptance Criteria**:
- [ ] All integration tests passing
- [ ] No security vulnerabilities identified
- [ ] Performance acceptable for expected load
- [ ] Documentation updated
- [ ] Ready for production use

**Implementation Notes**:
- Test with actual file uploads, not mocked data
- Use security testing tools if available
- Document any performance limitations
- Update README with new endpoint information

**Dependencies**:
- All previous steps must be complete
