# TODO - pyupload

## v0.1 Initial feature parity implementation

### Planning & Setup
- [x] Document application overview
- [x] Document legacy database schema
- [x] Document initial feature parity requirements
- [x] Research and select Python web/API framework
- [x] Research and select Front-end strategy (HTMX)
- [x] Establish development environment with Docker Compose
- [x] Implement database models mapping to legacy schema
- [x] Implement core business logic layer (app/lib/)
- [x] Implement JWT authentication with access and refresh tokens
- [x] Implement automatic token refresh middleware
- [x] Create architectural plan for core upload functionality
- [ ] Upload backend: file storage, upload handler, models, image metadata extraction (partially complete - Steps 1-3 done, Steps 4-6 pending)
- [ ] Upload endpoints: API and UI (POST endpoints for file receive)
- [ ] Upload widget UI: drag-and-drop form with file list and status
- [ ] File browsing: list and display uploaded files
- [ ] File viewing and delivery: view/download uploaded files
- [ ] Test coverage and validation

## Frontend Scaffolding
- [x] Integrate Tailwind CSS build system with automatic watching
- [x] Integrate Alpine.js for client-side interactivity
- [x] Convert base template from Bootstrap to Tailwind
- [x] Implement navbar with container-constrained content
- [x] Implement responsive navbar (mobile/sm/md breakpoints)
- [ ] Refine mobile breakpoint styling (needs content first)
- [ ] Add full navigation menu access at small breakpoint (currently only Upload visible)
- [ ] Implement dynamic Browse dropdown text based on active route
- [ ] Add conditional rendering for authenticated vs. anonymous users

## Future Authentication Enhancements
- [ ] Migrate to pwdlib recommended password hashing algorithms
- [ ] Implement configurable password complexity requirements (uppercase/lowercase/numbers/special chars)
- [ ] Implement two-factor authentication (2FA) support

## Future Upload Enhancements (Beyond simplegallery)
- [ ] Add HTMX upload progress bars (xhr:loadstart/loadend events) - Phase 1.5
- [ ] Implement parallel batch processing (asyncio.gather) - Phase 2
- [ ] Implement on-demand image thumbnail generation with filesystem caching - Phase 2
- [ ] Implement cache cleanup scheduler job (remove cached files after X days inactivity) - Phase 2
- [ ] Implement archive extraction on upload (ZIP, TAR, TAR.GZ) with nested support - Future
- [ ] Implement image watermarking for large images - Future
- [ ] Implement EXIF data extraction and storage - Future
- [ ] Implement image rotation/transformation endpoints - Future

## Future Collections & Organization (Beyond simplegallery)
- [ ] Implement collection/tagging system API endpoints
- [ ] Implement collection/tagging UI (create, edit, assign to files)
- [ ] Implement batch assignment (tag multiple files at once)
- [ ] Implement file search functionality

## Future Permissions & Sharing (Beyond simplegallery)
- [ ] Implement private/public permissions with shareable links
- [ ] Implement link-based sharing with optional expiration
- [ ] Implement granular access control (view, download, manage)
- [ ] Implement download statistics tracking

## Potential nice-to-have features that are not planned at this time.
- [ ] Implement S3/cloud storage backends
- [ ] Implement file integrity checking (checksums/verification)
- [ ] Implement virus/malware scanning integration
- [ ] Implement rate limiting and DDoS protection
- [ ] Implement audit logging for file operations
