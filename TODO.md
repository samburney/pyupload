# TODO - pyupload

## Current Release (v0.1)

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
- [ ] Implement file download/serving endpoints (GET /get/{id}/{filename})
- [ ] Remove temporary /files/ static route before release

---

## Future Release (v0.2)

### Upload Enhancements
- [ ] HTMX upload progress bars
- [ ] Parallel batch processing
- [ ] On-demand image thumbnail generation
- [ ] Cache cleanup scheduler

### Collections & Organization
- [ ] Collection/tagging system
- [ ] File search functionality

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
- [ ] Implement access control for private files (owner-only access)
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
