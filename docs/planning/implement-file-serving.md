# Implementation Plan: File Serving Endpoint

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
- `app/ui/files.py` (new)
- `app/api/files.py` (new)
- `app/lib/file_serving.py` (new)
- `app/main.py`

**Tasks**:
1. [ ] Create file serving logic in `app/lib/file_serving.py`
2. [ ] Implement UI endpoint GET `/get/{id}/{filename}` (optional filename)
3. [ ] Implement API endpoint GET `/api/v1/files/{id}/{filename}` (optional filename)
4. [ ] Validate upload ID exists in database
5. [ ] Use filename from URL if provided, otherwise use `Upload.originalname`
6. [ ] Sanitize filename to prevent injection attacks
7. [ ] Check file exists on filesystem using `Upload.filepath`
8. [ ] Return FileResponse with appropriate headers
9. [ ] Handle errors (404 for missing files, 500 for filesystem errors)
10. [ ] Register routers in main.py

**Tests**:
1. [ ] Test successful file serving for existing upload
2. [ ] Test serving with custom filename in URL
3. [ ] Test serving without filename (uses originalname)
4. [ ] Test 404 for non-existent upload ID
5. [ ] Test 404 for missing file on filesystem
6. [ ] Test filename sanitization prevents injection
7. [ ] Test both UI and API endpoints work identically

**Acceptance Criteria**:
- [ ] Both UI and API endpoints serve files successfully
- [ ] Filename can be customized in URL for SEO
- [ ] Fallback to originalname when no filename provided
- [ ] Proper error handling for all failure cases
- [ ] All tests passing

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
- `app/lib/file_serving.py`
- `app/lib/auth.py` (if needed)

**Tasks**:
1. [ ] Get current user from request (authenticated or anonymous)
2. [ ] Check if upload is private (private=1)
3. [ ] If private, verify current user is the owner
4. [ ] Return 403 Forbidden if unauthorized
5. [ ] Allow access if public or user is owner
6. [ ] Handle edge cases (deleted users, etc.)

**Tests**:
1. [ ] Test public file accessible to anonymous users
2. [ ] Test public file accessible to authenticated users
3. [ ] Test private file accessible to owner
4. [ ] Test private file returns 403 for other authenticated users
5. [ ] Test private file returns 403 for anonymous users

**Acceptance Criteria**:
- [ ] Private files only accessible to owners
- [ ] Public files accessible to all
- [ ] Proper 403 errors for unauthorized access
- [ ] All access control tests passing

**Implementation Notes**:
- Use `get_current_user_from_request()` to get user (returns None for anonymous)
- Compare `upload.user_id` with `current_user.id`
- Admin access to all files is out of scope (future enhancement)

**Dependencies**:
- Step 1 must be complete

---

## Step 3: Implement View Counter

**Files**: 
- `app/lib/file_serving.py`
- `app/models/uploads.py` (if needed)

**Tasks**:
1. [ ] Increment `viewed` field on successful file delivery
2. [ ] Use atomic update to prevent race conditions
3. [ ] Only increment for successful responses (not 404/403)
4. [ ] Do NOT increment when owner views their own file
5. [ ] Handle database errors gracefully

**Tests**:
1. [ ] Test view counter increments on file access by non-owner
2. [ ] Test view counter increments for anonymous users
3. [ ] Test view counter does NOT increment for owner views
4. [ ] Test view counter doesn't increment on 404
5. [ ] Test view counter doesn't increment on 403
6. [ ] Test atomic increment (concurrent requests)
7. [ ] Test view counter visible in upload metadata

**Acceptance Criteria**:
- [ ] View counter increments on each successful file delivery by non-owners
- [ ] Owner views do not increment counter
- [ ] Counter is atomic and thread-safe
- [ ] No increment on error responses
- [ ] All tests passing

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

**Files**: 
- `app/lib/file_serving.py`

**Tasks**:
1. [ ] Detect MIME type from file extension using `mimetypes` module
2. [ ] Set Content-Type header appropriately
3. [ ] Set Content-Disposition header based on file type and download parameter
4. [ ] Support `?download=1` query parameter to force download
5. [ ] Default to inline for browser-renderable types (images, videos, audio, PDF)
6. [ ] Default to attachment for non-renderable types
7. [ ] Set cache headers (1 hour, private for private files, public for public)
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
