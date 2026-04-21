# TODO - pyupload

## Current Release (v0.1) - Feature Parity with simplegallery

### Frontend Scaffolding
- [ ] Refine mobile breakpoint styling *(partial: CSS component styles migrated to `@utility` rules; responsive `md:max-lg:` modifiers added to view-page sidebar components; default Tailwind breakpoints restored; breakpoint debug indicator added; global anchor base styles intentionally removed for normalisation — needs re-establishing before merge)*
- [ ] Complete responsive navigation menu
- [ ] Add conditional rendering for authenticated vs. anonymous users

### Gallery & Discovery Pages (v0.1)
- [ ] Handle missing/broken image metadata in gallery with placeholder UX *(partial: `/get` now returns handled `422` image/HTML fallback responses with regression tests; gallery-card UX refinement still pending)*
- [x] Random uploads page (/random)
- [ ] Popular uploads page (/popular - most viewed)
- [ ] All uploads page (/all - latest public uploads)

### Static Content Pages (v0.1)
- [ ] About page
- [ ] Privacy Policy page
- [ ] Terms of Service page
- [ ] Contact page

---

## Future Release (v0.2) - Extended Feature Parity

### Gallery & Discovery Pages
- [ ] Sort and filter options (newest, most viewed, file type)
- [ ] Search functionality
  - [ ] Keyword search across titles, descriptions
  - [ ] Tag-based search

### Collections & Organization
- [x] Tags navbar link and browsing page (/tags)
- [x] Collections navbar link and browsing page (/collections)
- [ ] Collection management UI *(partial: collection assignment (add/remove) implemented via upload view page; collection creation possible via same UI; collection browsing implemented; edit and delete not yet implemented)*
  - [ ] Create/edit/delete collections *(partial: collection creation supported via upload view page; browsing at `/collections` and `/collections/view/{name_unique}` implemented)*
  - [x] Collection browsing pages
- [ ] Tag system UI *(partial: inline tag editing and read-only display on upload view page implemented; any authenticated user can tag any upload; tag browsing implemented; standalone management pages remain)*
  - [x] Tag browsing pages
  - [ ] Tag creation and management (standalone admin/browse pages)

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

### Database & ORM
- [ ] Upgrade to Tortoise ORM 1.x and built-in migrations *(serializer compatibility to confirm)*

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
- [ ] Wire up `build_qs_filter` stub in `app/ui/common/gallery.py` — parses request query string into a Tortoise `Q` object for use as a `context_filter` (uploader, private, date range, etc.).
- [ ] Investigate potential double-counting of partially-selected collections in the `buttonText` getter of `combo-selector.js` — items in `partially_selected` may also be added to `selected` via `x-model`, inflating the displayed count.
- [ ] Provide user feedback when some collection IDs are invalid/not owned in `PATCH /uploads/{id}/collection` (currently silently processes valid IDs and discards errors).
- [ ] Make home gallery page size user-configurable. *(partial: `infinite_scroll` flag added to `PaginationParams`; pagination component switches between infinite scroll and standard page controls; an "all" option would set `infinite_scroll=True` on the relevant view)*
- [ ] Make home gallery private-upload inclusion user-configurable (currently, logged-in users always see their own private uploads mixed into the home page feed).
- [ ] Replace `?modal=true` query parameter on `/view/{id}/{filename}` with HTMX response headers to consolidate modal and full-page view into a single endpoint.
- [ ] Scheduler: delete files owned by abandoned users when marked private.
- [ ] Fix/remove navbar links to unimplemented routes (`/uploads`, `/search`) until their pages are implemented.
- [x] Handle non-unique original names in archives
- [ ] Debug audio file handling.  An MP3 file was identified as `application/octet-stream`.  May just be a one off, but worth checking.
- [ ] Clean up Pydantic serialisation for Tortiose ORM models.  We originally used the build in serialisation which was clunky and since switched to `tortoise-serializer`.  We should switch everything to `tortoise-serializer` and clean up the dependencies of the old method.
- [ ] Migrate all hard-coded paths to `request.url_for()`
- [ ] Add share button for download archives.  Should pop up a modal with a clipboard button for each archive type.  Rather than just copy a URL, the button needs to fire off a archive generation request which then populates the URL box and can be copied to the clipboard (Or is copied automatically).
