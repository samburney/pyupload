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
- [ ] File storage backend (partially complete - Steps 1-3 done; Steps 4-6 pending)
- [ ] Upload endpoints (API and UI)
- [ ] Upload widget UI with progress feedback
- [ ] File browsing and display
- [ ] File viewing and delivery
- [ ] Test coverage and validation

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
