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
- [ ] Implement file download/serving endpoint (GET /get/{id}/{filename})
  - [ ] View counter increment on file delivery
  - [ ] Access control for private files (owner-only)
  - [ ] Proper MIME type handling
- [ ] Individual upload detail/view page
  - [ ] Display file metadata (size, dimensions, type, view count)
  - [ ] Social/direct link sharing options
  - [ ] Inline editing for title/description (owner only)
  - [ ] Privacy toggle (private/public) for owners
  - [ ] Delete button for owners/admins
- [ ] Remove temporary /files/ static route before release

### Access Control & Privacy
- [ ] Implement privacy enforcement for file serving
  - [ ] Private files only accessible to owner
  - [ ] Public files accessible to all
- [ ] Delete functionality for uploads (owners/admins only)

---

## Future Release (v0.2) - Extended Feature Parity

### Gallery & Discovery Pages
- [ ] Home page - Latest public uploads gallery
- [ ] Random uploads page
- [ ] Popular uploads page (most viewed)
- [ ] Search functionality
  - [ ] Keyword search across titles, descriptions
  - [ ] Tag-based search

### Collections & Organization
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

- [ ] S3/cloud storage backends
- [ ] File integrity checking (checksums/verification)
- [ ] Virus/malware scanning integration
- [ ] Rate limiting and DDoS protection
- [ ] Audit logging for file operations

---

## Fixes or Minor Enhancements

(None currently identified)
