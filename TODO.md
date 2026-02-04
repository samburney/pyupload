# TODO - pyupload

## Current Release (v0.1) - Feature Parity with simplegallery

### Planning & Foundation
- [x] Document application overview
- [x] Document legacy database schema
- [x] Document initial feature parity requirements
- [x] Research and select Python web/API framework
- [x] Research and select front-end strategy
- [x] Establish development environment with Docker Compose
- [x] Implement database models mapping to legacy schema
- [x] Implement core business logic layer
- [x] Implement JWT authentication with access and refresh tokens
- [x] Implement automatic token refresh middleware
- [x] Create architectural plan for core upload functionality

### Frontend Scaffolding
- [x] Integrate Tailwind CSS build system
- [x] Integrate Alpine.js for client-side interactivity
- [x] Convert base template from Bootstrap to Tailwind
- [x] Implement responsive navbar
- [ ] Refine mobile breakpoint styling
- [ ] Complete responsive navigation menu
- [ ] Add conditional rendering for authenticated vs. anonymous users

### Core Upload Functionality
- [x] Infrastructure foundation (Steps 1-5): File storage abstraction, upload handler, Upload/Image models, model registration — 83 passing tests
  - [x] File storage backend (filename generation, path construction, quota validation) — 16 tests
  - [x] Upload handler (single/batch upload, error recovery, cleanup) — 22 tests
  - [x] Upload model with metadata validation — 21 tests
  - [x] Image model with relationships — 14 tests
  - [x] Model imports and Tortoise ORM registration
- [x] Image metadata extraction (Step 6) — 14 passing tests
- [x] Upload endpoints - API and UI (Steps 7-8) — 30 passing tests
  - [x] API upload endpoint (POST /api/v1/uploads) — 12 tests
  - [x] UI upload endpoints (GET/POST /upload) — 18 tests
- [x] Upload widget UI with progress feedback (Step 9) — 30 passing tests
- [x] File browsing and gallery display (Step 10) — 5 passing tests
- [x] Basic configuration and transactional cleanup (Steps 11-12)
- [x] Scheduled maintenance jobs (Orphaned file cleanup) — 9 passing tests
- [x] Manual testing and security review (Step 13)
- [x] **Core upload functionality complete (495/495 tests passing)**

### File Serving & Viewing (Critical for v0.1)
- [x] Implement file download/serving endpoint (GET /get/{id}/{filename})
  - [x] View counter increment on file delivery
  - [x] Access control for private files (owner-only)
  - [x] Proper MIME type handling
  - [x] `/download/` endpoint for forced downloads
  - [x] Cache-Control headers (public/private, 1 hour)
  - [x] Automatic Last-Modified and ETag headers (via FileResponse)
- [x] API metadata endpoint (GET /api/v1/files/{id})
  - [x] Returns file metadata with absolute URLs
  - [x] Enriched fields (is_image, is_private, is_owner)
- [x] Remove temporary /files/ static route ✅
- [x] Integration tests and security review ✅
  - [x] Upload → View → Download workflow tests
  - [x] Private file access control tests (multi-user)
  - [x] Security: Path traversal prevention verified
  - [x] Security: Access control bypass prevention verified
  - [x] Security: SQL injection protection verified
  - [x] Edge cases: Special characters, concurrent access, missing files
- [x] **File serving complete (569/569 tests passing, 74 file serving tests)**
- [ ] Individual upload detail/view page
  - [ ] Display file metadata (size, dimensions, type, view count)
  - [ ] Social/direct link sharing options
  - [ ] Inline editing for title/description (owner only)
  - [ ] Privacy toggle (private/public) for owners
  - [ ] Delete button for owners/admins

### Gallery & Discovery Pages (v0.1)
- [ ] Random uploads page (/random)
- [ ] Popular uploads page (/popular - most viewed)
- [ ] All uploads page (/all - latest public uploads)

### Static Content Pages (v0.1)
- [ ] About page
- [ ] Privacy Policy page
- [ ] Terms of Service page
- [ ] Contact page

### Access Control & Privacy
- [x] Implement privacy enforcement for file serving
  - [x] Private files only accessible to owner
  - [x] Public files accessible to all
  - [x] Security review complete (path traversal, access bypass, SQL injection)
- [ ] Delete functionality for uploads (owners/admins only)

---

## Future Release (v0.2) - Extended Feature Parity

### Gallery & Discovery Pages
- [ ] Home gallery page (latest public uploads)
- [ ] Sort and filter options (newest, most viewed, file type)
- [ ] Random uploads page
- [ ] Popular uploads page (most viewed)
- [ ] Search functionality
  - [ ] Keyword search across titles, descriptions
  - [ ] Tag-based search

### Collections & Organization
- [ ] Tags navbar link and browsing page (/tags)
- [ ] Collections navbar link and browsing page (/collections)
- [ ] Collection management UI
  - [ ] Create/edit/delete collections
  - [ ] Add/remove uploads from collections
  - [ ] Collection browsing pages
- [ ] Tag system UI
  - [ ] Tag creation and management
  - [ ] Tag browsing pages
  - [ ] Inline tag editing on upload view page

### Image Processing & Transformations
- [ ] Dynamic image resizing (on-the-fly via URL parameters)
- [ ] Format conversion (deliver files in different formats)
- [ ] Image rotation endpoints
  - [ ] Update metadata (width/height swap)
  - [ ] Cache invalidation after rotation
- [ ] On-demand thumbnail generation
- [ ] Cache cleanup scheduler

### Upload Enhancements
- [ ] HTMX upload progress bars
- [ ] Parallel batch processing
- [ ] Loading states and transitions for all HTMX interactions

---

## Future Enhancements

### Authentication
- [ ] Migrate to pwdlib recommended password hashing
- [ ] Configurable password complexity requirements
- [ ] Two-factor authentication (2FA)

### Advanced Upload Features
- [ ] Archive extraction on upload (ZIP, TAR, TAR.GZ)
- [ ] Image watermarking
- [ ] EXIF data extraction and storage
- [ ] Image rotation/transformation endpoints

### Permissions & Sharing
- [ ] Admin access to all files (override privacy settings)
- [ ] Private/public permissions with shareable links
- [ ] Link-based sharing with optional expiration
- [ ] Granular access control (view, download, manage)
- [ ] Download statistics tracking

---

## Potential Future Enhancements

- [ ] Social media share buttons (Twitter, Facebook, Reddit, etc.)
- [ ] S3/cloud storage backends
- [ ] File integrity checking (checksums/verification)
- [ ] Virus/malware scanning integration
- [ ] Rate limiting and DDoS protection
- [ ] Audit logging for file operations

---

## Fixes or Minor Enhancements

- [ ] Review refresh_token functionality.  Sessions appear to be getting logged out after 30 minutes, but the refresh token is set to expire in 7 days.
      This could indicate that the refresh_token logic is not working as expected.
