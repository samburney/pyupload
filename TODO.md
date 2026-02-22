# TODO - pyupload

## Current Release (v0.1) - Feature Parity with simplegallery

### Frontend Scaffolding
- [ ] Refine mobile breakpoint styling
- [ ] Complete responsive navigation menu
- [ ] Add conditional rendering for authenticated vs. anonymous users

### File Serving & Viewing (Critical for v0.1)
- [ ] Individual upload detail/view page *(partial: full detail template with file preview, metadata panel, download dropdown, privacy enforcement, and SEO redirect implemented; sharing, inline editing, privacy toggle, delete, and view-page tests are not yet implemented)*
  - [x] Display file metadata (size, dimensions, type, view count)
  - [ ] Social/direct link sharing options
  - [ ] Inline editing for title/description (owner only)
  - [ ] Privacy toggle (private/public) for owners
  - [ ] Delete button for owners/admins

### Image Processing
- [x] Image rotation API endpoint (`POST /api/v1/images/{id}/rotate`) with metadata update and cache invalidation

### Gallery & Discovery Pages (v0.1)
- [ ] Handle missing/broken image metadata in gallery with placeholder UX *(partial: `/get` now returns handled `422` image/HTML fallback responses with regression tests; gallery-card UX refinement still pending)*
- [ ] Random uploads page (/random)
- [ ] Popular uploads page (/popular - most viewed)
- [ ] All uploads page (/all - latest public uploads)

### Static Content Pages (v0.1)
- [ ] About page
- [ ] Privacy Policy page
- [ ] Terms of Service page
- [ ] Contact page

### Access Control & Privacy
- [ ] Delete functionality for uploads (owners only; admin override tracked under Future Enhancements)

---

## Future Release (v0.2) - Extended Feature Parity

### Gallery & Discovery Pages
- [ ] Sort and filter options (newest, most viewed, file type)
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
- [ ] Expand processing support to all Pillow-compatible image formats
- [ ] On-demand thumbnail generation
- [ ] Cache cleanup scheduler

### Upload Enhancements
- [ ] HTMX upload progress bars
- [ ] Parallel batch processing
- [ ] Loading states and transitions for all HTMX interactions

### Upload view enhancements
- [ ] Provide 'preview'-like viewing of text and markdown files from gallery views

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
- [ ] Make home gallery page size user-configurable.
- [ ] Scheduler: delete files owned by abandoned users when marked private.
- [ ] Fix/remove navbar links to unimplemented routes (`/uploads`, `/search`, `/tags`, `/collections`) until their pages are implemented.
- [x] Refactor `app/lib/file_serving.py` to raise typed exceptions instead of returning responses directly, eliminating its `app/lib → app/ui` import of `error_response_for_get`.
- [ ] Refactor module dependencies for clean layer separation and no circular imports *(see `docs/planning/implement-inheritance-refactor.md`)*.
