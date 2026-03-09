# TODO - pyupload

## Current Release (v0.1) - Feature Parity with simplegallery

### Frontend Scaffolding
- [ ] Refine mobile breakpoint styling *(partial: CSS component styles migrated to `@utility` rules; responsive `md:max-lg:` modifiers added to view-page sidebar components; default Tailwind breakpoints restored; breakpoint debug indicator added; global anchor base styles intentionally removed for normalisation — needs re-establishing before merge)*
- [ ] Complete responsive navigation menu
- [ ] Add conditional rendering for authenticated vs. anonymous users

### File Serving & Viewing (Critical for v0.1)
- [ ] Individual upload detail/view page *(partial: view page componentised into reusable template components; file preview, metadata panel, download dropdown, privacy enforcement, SEO redirect, image rotation UI, direct-link sharing modal, inline tag editing, collection assignment UI, owner privacy toggle, description inline editing with max-length and validation error feedback, and delete functionality (with confirmation modal) all implemented; CSS architecture refactored to `@utility` rules with responsive `md:max-lg:` modifiers for sidebar components; broader view-page route tests remain)*
  - [x] Display file metadata (size, dimensions, type, view count)
  - [x] Image rotation UI (owner only)
  - [x] Delete button for owners
  - [x] Inline tag editing (owner only)
  - [x] Direct link sharing options
  - [x] Inline editing for description/title (owner only) *(description doubles as title — `upload.display_name` returns `description` if set, else `originalname`)*
  - [x] Privacy toggle (private/public) for owners

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
- [x] Delete functionality for uploads (owners only; admin override tracked under Future Enhancements)

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
- [ ] Collection management UI *(partial: collection assignment (add/remove) implemented via upload view page; collection creation possible via same UI; collection browsing, edit, and delete not yet implemented)*
  - [ ] Create/edit/delete collections *(partial: collection creation supported via upload view page)*
  - [x] Add/remove uploads from collections
  - [ ] Collection browsing pages
- [ ] Tag system UI *(partial: inline tag editing and read-only display on upload view page implemented; any authenticated user can tag any upload; tag browsing and standalone management pages remain)*
  - [ ] Tag browsing pages
  - [ ] Tag creation and management (standalone admin/browse pages)
  - [x] Inline tag editing on upload view page (any authenticated user)

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
- [ ] Provide user feedback when some collection IDs are invalid/not owned in `PATCH /uploads/{id}/collection` (currently silently processes valid IDs and discards errors).
- [ ] Make home gallery page size user-configurable.
- [ ] Make home gallery private-upload inclusion user-configurable (currently, logged-in users always see their own private uploads mixed into the home page feed).
- [ ] Replace `?modal=true` query parameter on `/view/{id}/{filename}` with HTMX response headers to consolidate modal and full-page view into a single endpoint.
- [ ] Scheduler: delete files owned by abandoned users when marked private.
- [ ] Fix/remove navbar links to unimplemented routes (`/uploads`, `/search`, `/tags`, `/collections`) until their pages are implemented.
- [x] Refactor `app/lib/file_serving.py` to raise typed exceptions instead of returning responses directly, eliminating its `app/lib → app/ui` import of `error_response_for_get`.
- [x] Refactor module dependencies for clean layer separation and no circular imports: `app/lib/file_io.py` created as pure I/O layer; `get_filename`, `get_file_instance`, `get_file_size`, `get_file_mime_type`, `delete_file` moved from `file_storage.py` to `file_io.py`.
