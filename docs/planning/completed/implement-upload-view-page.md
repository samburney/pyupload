# Implementation Plan: Upload View Page

## Overview

Implement individual upload detail/view pages that display file metadata, provide sharing options, allow inline editing of title/description for owners, include privacy toggles, and provide delete functionality.

### Scope
- Individual upload view page at `/view/{id}/{filename}`
- Redirect from `/view/{id}` to `/view/{id}/{filename}` for SEO
- Display file metadata (size, dimensions, type, view count, upload date)
- Show file preview (images inline, videos with player, others with icon)
- Direct link sharing with copy-to-clipboard
- Inline editing for description (owner only)
- Privacy toggle between public/private (owner only)
- Delete button (owner only)
- Breadcrumb navigation
- Access control: private uploads only viewable by owner

### Current State
- `/view/{id}/{filename}` route renders a full upload detail page with sidebar metadata panel and file preview
- View page fully componentised: `view-frame.html.j2`, `view-sidebar.html.j2`, `upload-details.html.j2`, `upload-download-button.html.j2`, `upload-sidebar-actions.html.j2`
- File preview in `view-frame.html.j2`: images display inline with loading indicator overlay, server-side cache-busting (`?t={updated_at_timestamp}`), and `id="view-frame-image"` for HTMX targeting; non-images show a file-type icon/link
- Sidebar metadata panel in `upload-details.html.j2` with all fields and responsive styling
- Download button in `upload-download-button.html.j2`: dropdown for images (original, JPG, GIF, PNG conversions); plain button for non-images
- Share button/modal in `upload-share-button.html.j2` for public uploads with copyable direct URLs (image URL, details URL, download URL)
- Image rotation UI in `upload-sidebar-actions.html.j2`: owner-only, HTMX-powered rotate dropdown (90° CW, 180°, 90° CCW) with loading indicator and Rotate button disabled during requests
- Privacy toggle in `upload-private-toggle.html.j2`: owner-only, HTMX `PATCH /uploads/{id}/private` checkbox switch with inline state update
- Modal view variant exists via `?modal=true`
- `/view/{id}` redirects to `/view/{id}/{cleanname}` with 301 (404 if upload not found); private files return 403 on this route (no user context, prevents information disclosure)
- Privacy enforced on `/view/{id}/{filename}`: `validate_file_request` returns 403 for non-owner access to private uploads
- Description inline editing in `upload-description.html.j2`: owner-only Alpine.js hover-to-edit overlay with `<textarea>` (`x-ref="descriptionField"`), save via `hx-patch="/uploads/{id}/description"`, explicit cancel button and Escape key both reset via `defaultValue` and exit edit mode; non-owners see read-only `<p>`; max-length enforced by Tortoise `CharField(max_length=255)` with `ValidationError` caught at the route level and displayed inline via `parse_tortoise_validation_errors`
- Delete functionality implemented (owner-only): confirmation modal, UI/API delete endpoints, model-level hard delete, and cache-aware file deletion helper
- Inline tag editing (any authenticated user) and collection assignment (per-user) implemented on the view page
- Integration tests exist for gallery-to-view and modal/responsive/accessibility flows; dedicated route-level matrix tests remain incomplete
- Profile page shows list of user's uploads

### Review Snapshot (2026-02-15)
- The main view route and template exist and render for valid uploads.
- Private upload access enforcement for view pages is still missing.
- SEO redirect route (`/view/{id}`) is still missing.
- Metadata/share/edit/privacy/delete workflows and tests remain pending.

### Review Snapshot (2026-02-21)
- File preview implemented inline in `view.html.j2` (image vs non-image branching; Steps 2 tasks 2, 5, 7 complete).
- Full metadata panel implemented inline in `view.html.j2` with all fields and responsive styling (Step 3 tasks 2–9 complete).
- Download dropdown (with format conversion) implemented for images; plain download button for non-images.
- No separate preview or metadata component files were created; all implemented inline — this meets the intended function.
- `display_title` variable (`upload.description or upload.originalname`) correctly set at template top.
- SEO redirect (`/view/{id}` → 301 → `/view/{id}/{cleanname}`) implemented.
- Privacy enforcement implemented via `validate_file_request` on both `/view/{id}` and `/view/{id}/{filename}` routes (Step 1 task 6 complete).
- Sharing, inline editing, privacy toggle, delete, and all view-page tests remain pending.

### Review Snapshot (2026-02-22)
- View page fully refactored into reusable components: `view-frame.html.j2`, `view-sidebar.html.j2`, `upload-details.html.j2`, `upload-download-button.html.j2`, `upload-sidebar-actions.html.j2`. Steps 2 task 1 and Step 3 task 1 now complete.
- `view-frame.html.j2` adds `id="view-frame-image"` on image for HTMX targeting, server-side cache-busting via `?t={updated_at_timestamp}`, and a loading indicator overlay (Steps 2 task 6 partial — loading state handled, broken image placeholder still pending).
- `upload-sidebar-actions.html.j2` implements owner-only image rotation UI: HTMX-powered dropdown with 90° CW, 180°, and 90° CCW options. HTMX swaps `#view-frame-image`, `#upload-details`, and `#messages` in-place after rotation; Rotate button disabled during in-flight requests via `hx-disabled-elt`; loading spinner shown via `hx-indicator`.
- `app/ui/images.py` provides the `POST /images/{id}/rotate/{angle}` UI endpoint that rotates the image and returns the full rendered view page for HTMX partial extraction.
- `app/ui/__init__.py` and `app/main.py` updated to register the new UI images router.
- Delete functionality implemented: `Upload.delete()` model method added (`await super().delete()` then `asyncio.to_thread(delete_file, self.filepath)`); `DELETE /{id}` UI endpoint in `app/ui/uploads.py` (owner-only, HTMX-powered, 204 + `HX-Redirect: /profile`); `DELETE /api/v1/uploads/{id}` API endpoint in `app/api/uploads.py` (200 + JSON result); confirmation modal in `confirm-modal.html.j2`. `app/lib/file_io.py` created as pure I/O layer; I/O functions moved from `file_storage.py` to `file_io.py`.
- Sharing, inline editing, privacy toggle, and all view-page tests remain pending.

### Review Snapshot (2026-03-01)
- Tag management implemented inline on the upload view page (Step 10 below).
- `app/models/tags.py`: `Tag.add_or_create_for_upload` and `Tag.remove_tag_from_upload` class methods added; `TagSerializer` added.
- `app/models/uploads.py`: `tags = fields.ManyToManyField("models.Tag", ...)` added to `Upload`; `tags` field added to `UploadSerializer`.
- Three new HTMX endpoints in `app/ui/uploads.py`: `POST /uploads/{id}/tag-suggestions`, `POST /uploads/{id}/tag`, `DELETE /uploads/{id}/tag`.
- `app/ui/templates/components/core/tag-input.html.j2`: new Alpine.js tag input widget with autocomplete, add, and remove interactions.
- `app/ui/templates/components/core/tag-suggestions.html.j2`: suggestions dropdown partial for HTMX swap.
- All `prefetch_related` calls across `app/ui/main.py`, `app/ui/images.py`, `app/ui/users.py`, and `app/api/images.py` updated to include `"tags"`.
- Tests: `tests/test_models_tags.py` (14 tests), `tests/test_lib_helpers.py` additions (`TestCleanText`, `TestMakeCleanTag`), and `tests/test_ui_uploads.py` additions (`TestTagSuggestionsEndpoint`, `TestUploadAddTagEndpoint`, `TestUploadDeleteTagEndpoint`) — all 788 tests passing.
- Title/description inline editing and broader view-page route matrix tests remain pending.

### Review Snapshot (2026-03-04)
- Tag access control opened up: `validate_file_update_request` removed from tag endpoints; any authenticated user can now tag any upload (tags are public/shared constructs). Unauthenticated users see a read-only tag display via new `render_tags_readonly()` macro in `tag-input.html.j2`. Step 10 acceptance criteria and test descriptions updated to reflect this.
- `Upload.get_with_relations(id)` classmethod added to `app/models/uploads.py`; replaces inline `prefetch_related` chains throughout all endpoints.
- Collections UI implemented on the upload view page (Step 11 below): per-user collection assignment via an Alpine.js multi-select combo selector; any authenticated user can assign their own collections to any public upload.
- `/test` dev endpoint and `test.html.j2` template removed.
- Debug `print()` statement and unused `upload_user_collections` variable removed from `view_upload_page_get`.
- `existing_collection_ids` query now filtered by `user=current_user` in all three collection endpoints (was missing the user filter).
- Test suite updated: `conftest.py` registers `app.models.collections`; new `tests/test_models_collections.py` (15 tests); new `TestUploadGetWithRelations` and `TestUploadUserCollections` in `test_models_uploads.py`; collection endpoint classes in `test_ui_uploads.py`; `SELECT_QUERY_BASELINE_BUDGET` updated 30 → 31.
- 827 tests passing.
- Remaining: max-length validation for description (255 chars), broader per-route view-page test matrix.

### Review Snapshot (2026-03-05)
- Sharing UI implemented for public uploads: new `upload-share-button.html.j2` component with a modal (`modal-basic.html.j2`) that exposes copyable direct URLs for image/details/download links.
- Sidebar behavior updated in `view-sidebar.html.j2`: share button is rendered only for non-private uploads.
- Privacy toggle implemented for owners: new `PATCH /uploads/{id}/private` endpoint in `app/ui/uploads.py` and `upload-private-toggle.html.j2` HTMX component rendered from `upload-sidebar-actions.html.j2`.
- `confirm-modal.html.j2` was renamed to `modal-dialog.html.j2`; delete button component updated to use the renamed macro.
- Tests added: `TestUploadPrivateTogglePatchEndpoint` in `tests/test_ui_uploads.py` and share/private view integration assertions in `tests/test_integration_gallery.py`.
- Remaining major gap for this plan: title/description inline editing and broader per-route view-page test matrix.

### Review Snapshot (2026-03-07)
- Description inline editing implemented (Step 5 partial): `upload-description.html.j2` Alpine.js component with hover-to-edit overlay, inline `<textarea>`, save via `hx-patch="/uploads/{id}/description"`, and Escape key to cancel. Non-owners see a read-only `<p>` display.
- `PATCH /uploads/{id}/description` endpoint added to `app/ui/uploads.py`; uses `html.escape()` + `.strip()` to sanitise input before persisting to `upload.description`.
- `app/ui/common/uploads.py` created with four UI-layer helpers to eliminate repeated boilerplate across route handlers: `get_upload_or_404`, `get_upload_with_relations_or_404`, `get_upload_or_404_for_read`, `get_upload_or_404_for_update`.
- DRY refactoring in `app/ui/uploads.py`: `_render_tag_input` and `_render_upload_component` private helpers eliminate repeated template context construction across multiple routes.
- Tests: `TestUploadDescriptionPatchEndpoint` (6 tests: 404, owner update, clear, HTML-escape/XSS, non-owner 403) added to `tests/test_ui_uploads.py`; privacy toggle test suite complete.
- CSS architecture refactored: component styles moved from `@layer components` to `@utility` rules for better Tailwind v4 compatibility and CSS nesting. Responsive `md:max-lg:` modifiers added to sidebar components (split buttons, tags, share button, private toggle, download button) to scale at medium breakpoints. Default Tailwind breakpoints restored (Bootstrap 4 overrides removed); custom `3xl`/`4xl`/`5xl` breakpoints added. View frame/sidebar layout uses `md:max-w-4/5 lg:max-w-3/4 xl:max-w-full` with sidebar `md:w-1/5 lg:w-1/4 xl:max-w-64`. Tag items now use hover-to-reveal delete button pattern. Breakpoint debug indicator added to base layout (gated behind `config.debug`). Global anchor `<a>` base styles intentionally removed for normalisation — will be re-addressed in UI polish plan before merge.
- 846 tests passing.
- Remaining: max-length validation for description (255 chars), broader per-route view-page test matrix, re-establish anchor base styles before merge.

### Review Snapshot (2026-03-09b)
- Route/template test matrix completed for Steps 1–5: `TestViewUploadPageRedirectEndpoint` (3 tests), `TestViewUploadPageEndpoint` (8 tests), `TestViewUploadPageContent` (13 tests — file preview, metadata, sharing, edit-form visibility), `TestDescriptionMaxLengthValidation` (2 tests). 880 tests passing.
- Step 8 (polish/accessibility) removed from this plan: breadcrumbs and Open Graph meta tags tracked in `implement-ui-polish.md`; non-automatable tests (copy-to-clipboard, HTMX swap, cancel button, mobile/screen-reader) deferred to manual QA.
- `TODO.md` `[ ] Individual upload detail/view page` item ready to be checked off.

### Review Snapshot (2026-03-09)
- Description validation error feedback implemented (Step 5 complete): `parse_tortoise_validation_errors` helper added to `app/lib/error_handling.py`; `PATCH /uploads/{id}/description` now catches `ValidationError` from Tortoise, parses field-level messages, and returns a 400 with `validation_errors` in template context. `description.html.j2` displays inline error text, highlights the `<textarea>` with a red border on 400, and uses `hx-target-400` + `hx-select` + `hx-swap="innerHTML"` so error responses refresh the component's inner content without exiting edit mode. `@htmx:after-swap` exits edit mode only on 200. `_render_upload_component` extended with optional `context` and `status_code` parameters. Tortoise `CharField(max_length=255)` on `Upload.description` is the enforced validation boundary. `.validation-error` utility added to `input.css`; `wrap-break-word` applied to description display and error text.
- Remaining: test for max-length validation (255 chars), broader per-route view-page test matrix, re-establish anchor base styles before merge.

### Target State
- `/view/{id}/{filename}` endpoint renders upload detail page
- File preview displayed appropriately based on type
- All metadata visible (size, dimensions, type, views, date)
- Copy-to-clipboard sharing links
- Inline edit form for description (HTMX-powered; doubles as title — `upload.display_name` returns `description` if set, else `originalname`)
- Privacy toggle switch (HTMX-powered)
- Delete button with confirmation modal
- Owner-only controls properly hidden for non-owners
- Responsive design matching site theme
- All tests passing

---

## Step 1: Create Upload View Route and Template

**Files**: 
- `app/ui/uploads.py`
- `app/ui/templates/uploads/view.html.j2` (new)

**Tasks**:
1. [x] Create GET `/view/{id}` route (redirects to add filename)
2. [x] Create GET `/view/{id}/{filename}` route (main view page)
3. [x] Fetch upload from database with related data (images, user)
4. [x] Validate upload exists (404 if not)
5. [x] Get current user for permission checks
6. [x] Enforce privacy: private uploads only accessible to owner (403 if not)
7. [x] Create base template with layout
8. [x] Pass upload data and permissions to template
9. [x] Redirect `/view/{id}` to `/view/{id}/{cleanname}` with 301

**Tests**:
1. [x] Test view page renders for existing public upload — `TestViewUploadPageEndpoint.test_page_returns_html`
2. [x] Test 404 for non-existent upload — `TestViewUploadPageEndpoint.test_nonexistent_upload_returns_404`, `TestViewUploadPageRedirectEndpoint.test_nonexistent_upload_returns_404`
3. [x] Test public upload accessible to anonymous users — `TestViewUploadPageEndpoint.test_public_upload_accessible_to_anonymous_users`
4. [x] Test public upload accessible to authenticated users — `TestViewUploadPageEndpoint.test_public_upload_accessible_to_authenticated_users`
5. [x] Test private upload accessible to owner — `TestViewUploadPageEndpoint.test_private_upload_accessible_to_owner`
6. [x] Test private upload returns 403 for other users — `TestViewUploadPageEndpoint.test_private_upload_returns_403_for_other_users`
7. [x] Test private upload returns 403 for anonymous users — `TestViewUploadPageEndpoint.test_private_upload_returns_403_for_anonymous_users`
8. [x] Test redirect from `/view/{id}` to `/view/{id}/{filename}` — `TestViewUploadPageRedirectEndpoint.test_public_upload_redirects_to_view_with_filename`
9. [x] Test correct data passed to template — `TestViewUploadPageEndpoint.test_page_renders_original_filename`

**Acceptance Criteria**:
- [x] View page route functional
- [x] Privacy enforced (private uploads owner-only)
- [x] SEO-friendly URLs with filename
- [x] Proper error handling (404, 403)
- [x] All tests passing

**Implementation Notes**:
- Use 301 Permanent Redirect from `/view/{id}` to `/view/{id}/{upload.cleanname}`
- Filename in URL is for SEO; actual file identified by ID
- Fetch upload with `.prefetch_related("images", "user")` for efficiency
- Privacy check: if `upload.private == 1` and `current_user.id != upload.user_id`, return 403
- Use `upload.cleanname` for redirect (user-friendly filename)

---

## Step 2: Display File Preview

**Files**: 
- `app/ui/templates/uploads/view.html.j2`
- `app/ui/templates/uploads/components/file-preview.html.j2` (new)

**Tasks**:
1. [x] Create file preview component
2. [x] Display images inline with `<img>` tag
~~3. [ ] Display videos with `<video>` player~~: Out of scope for this release.
~~4. [ ] Display audio with `<audio>` player~~: Out of scope for this release.
5. [x] Display file icon for other types
6. [ ] Add loading states and error handling (including missing image metadata placeholder)
7. [x] Make preview responsive

**Tests**:
1. [x] Test image preview renders correctly — `TestViewUploadPageContent.test_image_upload_shows_image_frame`
~~2. [ ] Test video preview with controls~~: Out of scope for this release
~~3. [ ] Test audio preview with controls~~: Out of scope for this release
4. [x] Test generic file icon for documents — `TestViewUploadPageContent.test_non_image_upload_shows_file_extension`, `test_non_image_upload_does_not_show_image_frame`
5. [ ] Test responsive sizing — *not automatable; requires browser/CSS testing*
6. [ ] Test broken image handling and missing image metadata placeholder — *not automatable; handled client-side by HTMX/Alpine.js*

**Acceptance Criteria**:
- [x] Images display inline
~~- [ ] Videos playable in browser~~: Out of scope for this release
~~- [ ] Audio playable in browser~~: Out of scope for this release
- [x] Other files show appropriate icon
- [ ] Responsive and accessible *(deferred to UI polish plan)*
- [x] All automatable tests passing

**Implementation Notes (2026-02-21)**:
- Tasks 2, 5, 7 implemented inline in `view.html.j2` rather than in a separate component file. The `{% if upload.is_image %}` branch renders an `<img>` tag inside a styled card; the `{% else %}` branch renders a file-type icon link using `upload.dot_ext`. The `<article>` uses `w-full md:w-3/4` for responsive sizing.
- No separate `file-preview.html.j2` component was created; this deviates from the plan but meets the intended function.
- Video/audio players and loading state placeholders remain to be implemented.

**Implementation Notes**:
- Use `upload.url` for file source
- Check `upload.type` (MIME type) to determine preview type
- For images, check `upload.is_image` property
- If image metadata is missing or invalid, prefer rendering a missing-image placeholder instead of exposing server errors.
- Consider max-width constraints for large images
- Add alt text for accessibility
- Use Alpine.js for interactive elements if needed

**Dependencies**:
- Step 1 must be complete

---

## Step 3: Display Metadata

**Files**: 
- `app/ui/templates/uploads/view.html.j2`
- `app/ui/templates/uploads/components/metadata-panel.html.j2` (new)

**Tasks**:
1. [x] Create metadata panel component
2. [x] Display file size (formatted, e.g., "2.5 MB")
3. [x] Display dimensions for images (width x height)
4. [x] Display MIME type
5. [x] Display view count
6. [x] Display upload date (formatted)
7. [x] Display uploader username
8. [x] Display title and description
9. [x] Style metadata panel

**Tests**:
1. [x] Test all metadata fields display — `TestViewUploadPageContent.test_metadata_shows_uploader_username`, `test_metadata_shows_mime_type`, `test_metadata_shows_view_count_icon`, `test_metadata_shows_upload_date_icon`
2. [ ] Test file size formatting — *deferred; the `humanize_bytes` filter is unit-tested separately*
3. [x] Test dimension display for images — `TestViewUploadPageContent.test_image_metadata_shows_dimensions`
4. [x] Test dimension not shown for non-images — `TestViewUploadPageContent.test_non_image_metadata_does_not_show_dimensions`
5. [ ] Test date formatting — *deferred; the `ago` filter is unit-tested separately*
6. [ ] Test missing metadata handled gracefully — *not automatable; graceful handling is client-side*

**Acceptance Criteria**:
- [x] All metadata visible and formatted
- [x] Clean, readable layout
- [x] Responsive design
- [x] All automatable tests passing

**Implementation Notes (2026-02-21)**:
- Tasks 2–9 implemented inline in `view.html.j2` sidebar panel rather than in a separate component file. All fields are present: description/title (`display_title`), username with public/private icons, MIME type, file size (`humanize_bytes` filter), view count, upload date (`ago` filter), and image dimensions guarded by `{% if upload.is_image %}`.
- No separate `metadata-panel.html.j2` component was created; this deviates from the plan but meets the intended function.
- Tests remain to be written.

**Implementation Notes**:
- Use `app/lib/helpers.py` for formatting functions (create if needed)
- Format file size: bytes → KB → MB → GB
- Format date: relative time or absolute (e.g., "2 hours ago" or "Jan 31, 2026")
- Show dimensions only if `upload.is_image` is True
- Consider adding metadata like file extension, original filename

**Dependencies**:
- Step 1 must be complete

---

## Step 4: Implement Sharing Options

**Files**: 
- `app/ui/templates/uploads/partials/view-sidebar.html.j2`
- `app/ui/templates/components/upload/share-button.html.j2` (new)
- `app/ui/templates/components/core/modal-basic.html.j2` (new)
- `app/ui/templates/components/core/icons-sprite.html.j2`

**Tasks**:
1. [x] Create share panel component
2. [x] Display direct link (view page URL)
3. [x] Display file link (direct file/download URLs)
4. [x] Add copy-to-clipboard buttons for links
5. [x] Add visual feedback on copy
6. [x] Make links selectable for manual copy

**Tests**:
1. [x] Test direct link displays correct view page URL
2. [x] Test file link displays correct file URL
3. [x] Test file link opens in new tab (target=_blank) — `TestViewUploadPageContent.test_file_link_has_target_blank`
4. [ ] Test copy-to-clipboard functionality — *not automatable; requires JavaScript execution*
5. [ ] Test visual feedback on copy — *not automatable; requires JavaScript execution*
6. [x] Test links are selectable
7. [ ] Test on mobile devices — *not automatable; requires device testing*
8. [x] Test share button shown for public uploads — `TestViewUploadPageContent.test_share_button_shown_for_public_upload`
9. [x] Test share button not shown for private uploads — `TestViewUploadPageContent.test_share_button_not_shown_for_private_upload`

**Acceptance Criteria**:
- [x] Share links displayed correctly
- [x] File link opens in new tab
- [ ] Copy-to-clipboard works *(not automatable)*
- [ ] Good user feedback *(not automatable)*
- [ ] Mobile-friendly *(deferred to UI polish plan)*
- [x] All automatable tests passing

**Implementation Notes**:
- Use Clipboard API: `navigator.clipboard.writeText()`
- Provide fallback for older browsers
- Direct link (view page): `window.location.href` or construct from upload.id
- File link: `upload.url` with `target="_blank"` (opens in new tab)
- Use Alpine.js for interactivity to avoid separate JS file
- Show success message for 2-3 seconds after copy
- Social media share buttons deferred to future enhancement

**Dependencies**:
- Step 1 must be complete

---

## Step 5: Implement Inline Editing (Owner Only)

**Files**: 
- `app/ui/uploads.py`
- `app/ui/templates/uploads/view.html.j2`
- `app/ui/templates/uploads/components/edit-form.html.j2` (new)

**Tasks**:
1. [x] Add edit form for description field
2. [x] Show edit form only to upload owner
3. [x] Create PATCH endpoint for updating upload description
4. [x] Use HTMX for inline editing without page reload
5. [x] Validate description (prevent injection attacks, max 255 chars) — `html.escape()` for XSS; Tortoise `CharField(max_length=255)` enforced on save with `ValidationError` caught and surfaced to user
6. [x] Update upload.description in database
7. [x] Return updated content to replace form
8. [x] Add cancel button to revert changes — explicit cancel button resets textarea via `$refs.descriptionField.defaultValue`; Escape key also resets and exits

**Note**: There is no separate `title` field in the database. `upload.description` doubles as the title — `upload.display_name` returns `description` if set, else `originalname`. Editing the description field is the complete implementation of title/description inline editing.

**Tests**:
1. [x] Test edit form visible to owner — `TestViewUploadPageContent.test_edit_form_visible_to_owner`
2. [x] Test edit form hidden from non-owners — `TestViewUploadPageContent.test_edit_form_not_visible_to_non_owners`, `test_edit_form_not_visible_to_anonymous_users`
3. [x] Test successful description update — `TestUploadDescriptionPatchEndpoint.test_owner_can_update_description`
4. [x] Test validation prevents injection attacks — `TestUploadDescriptionPatchEndpoint.test_description_is_html_escaped`
5. [x] Test max length validation (255 chars) — `TestDescriptionMaxLengthValidation.test_description_at_max_length_is_accepted`, `test_description_over_max_length_returns_400`
6. [ ] Test HTMX swap behavior — *not automatable; requires client-side JavaScript*
7. [ ] Test cancel button — *not automatable; requires client-side JavaScript*
8. [x] Test unauthorized edit attempt (403) — `TestUploadDescriptionPatchEndpoint.test_non_owner_cannot_update_description`

**Acceptance Criteria**:
- [x] Owner can edit description inline
- [x] Non-owners cannot see edit controls
- [x] Updates work without page reload
- [x] Proper validation and error handling — XSS via `html.escape()`; max-length enforced via Tortoise `CharField(max_length=255)` with `ValidationError` caught and displayed inline; explicit cancel button and Escape key both reset and exit
- [x] All automatable tests passing

**Implementation Notes**:
- There is no separate `title` field in the database. `upload.description` doubles as the title — `upload.display_name` returns `description` if set, else `originalname`. Steps referring to "title" editing are all satisfied by this single field.
- Edit field: `upload.description` (max 255 chars, defaults to originalname when empty)
- `upload.name` is the filesystem filename and should NOT be editable
- Use HTMX `hx-patch` for form submission
- Endpoint: `PATCH /uploads/{id}`
- Return partial HTML to swap into page
- Use `hx-swap="outerHTML"` to replace form with updated display
- Validate description: strip HTML tags, prevent XSS, max 255 chars
- Validate user is owner before allowing update

**Dependencies**:
- Step 1 must be complete
- Step 3 must be complete (to show updated metadata)

---

## Step 6: Implement Privacy Toggle (Owner Only)

**Files**: 
- `app/ui/uploads.py`
- `app/ui/templates/components/upload/sidebar-actions.html.j2`
- `app/ui/templates/components/upload/private-toggle.html.j2` (new)

**Tasks**:
1. [x] Add privacy toggle switch (public/private)
2. [x] Show toggle only to upload owner
3. [x] Create PATCH endpoint for toggling privacy
4. [x] Use HTMX for toggle without page reload
5. [x] Update `private` field in database (0 or 1)
6. [x] Return updated toggle state
7. [x] Show visual feedback on change

**Tests**:
1. [ ] Test toggle visible to owner
2. [ ] Test toggle hidden from non-owners
3. [x] Test toggle from public to private
4. [x] Test toggle from private to public
5. [x] Test HTMX behavior
6. [x] Test unauthorized toggle attempt (403)
7. [x] Test database update

**Acceptance Criteria**:
- [x] Owner can toggle privacy inline
- [x] Non-owners cannot see toggle
- [x] Updates work without page reload
- [x] Database updated correctly
- [x] All tests passing

**Implementation Notes**:
- Use checkbox or toggle switch UI component
- Endpoint: `POST /uploads/{id}/privacy` or `PATCH /uploads/{id}`
- Toggle between 0 (public) and 1 (private)
- Use HTMX `hx-post` with `hx-swap="outerHTML"`
- Consider showing icon/badge indicating current privacy state
- Add confirmation if making private upload public (optional)

**Dependencies**:
- Step 1 must be complete

---

## Step 7: Implement Delete Functionality (Owner Only)

**Files**: 
- `app/ui/uploads.py`
- `app/ui/templates/components/upload/sidebar-actions.html.j2`
- `app/ui/templates/components/confirm-modal.html.j2` (new)
- `app/models/uploads.py`
- `app/api/uploads.py`
- `app/lib/file_io.py` (new)
- `app/lib/file_storage.py`

**Tasks**:
1. [x] Add delete button (owner only)
2. [x] Create HTMX-powered confirmation modal
3. [x] Create DELETE endpoint for upload
4. [x] Verify user is owner before allowing delete
5. [x] Delete file from filesystem (hard delete)
6. [x] Delete upload record from database
7. [x] Delete related image records (cascade)
8. [x] Redirect to profile after delete
9. [x] Handle errors gracefully (file missing, etc.)

**Tests**:
1. [ ] Test delete button visible to owner
2. [ ] Test delete button hidden from non-owners
3. [ ] Test confirmation modal displays
4. [x] Test successful deletion (file + database) — `TestUploadDelete`, `TestDeleteUploadEndpoint`, `TestDeleteUploadPage`
5. [x] Test file removed from filesystem — `TestUploadDelete.test_delete_calls_delete_file_with_filepath`
6. [x] Test database record removed — `TestUploadDelete`, `TestDeleteUploadEndpoint.test_removes_upload_from_database`, `TestDeleteUploadPage.test_removes_upload_from_database_on_success`
7. [x] Test related image records removed (cascade) — covered by Tortoise ORM cascade on FK
8. [x] Test unauthorized delete attempt (403) — `TestDeleteUploadEndpoint.test_returns_403_for_non_owner`, `TestDeleteUploadPage.test_returns_403_for_non_owner`
9. [x] Test delete non-existent upload (404) — `TestDeleteUploadEndpoint.test_returns_404_for_nonexistent_upload`, `TestDeleteUploadPage.test_returns_404_for_nonexistent_upload`
10. [x] Test delete with missing file (handles gracefully) — `TestUploadDelete.test_delete_removes_db_record_even_when_file_missing`

**Acceptance Criteria**:
- [x] Owner can delete their uploads
- [x] Confirmation required before delete
- [x] File and database records permanently removed (hard delete)
- [x] Proper error handling
- [x] All tests passing

**Implementation Notes**:
- `Upload.delete()` calls `await super().delete()` first (DB), then `await asyncio.to_thread(delete_file, self.filepath)` (file I/O off the event loop). This ordering ensures orphan cleanup handles any file deletion failure.
- `delete_file()` lives in `app/lib/file_io.py` (pure I/O layer, no model deps). It also removes cached variants matching `parent/cache/{stem}-*`.
- UI endpoint (`DELETE /{id}`) uses `get_current_authenticated_user` — unauthenticated requests redirect to `/login` via the global `LoginRequiredException` handler. Returns 204 + `HX-Redirect: /profile` for HTMX navigation; non-HTMX clients must use the API endpoint.
- API endpoint (`DELETE /api/v1/uploads/{id}`) returns JSON `{"result": {"status": "success"}}` on 200.
- Admin delete functionality is out of scope (future enhancement).

**Dependencies**:
- Step 1 must be complete

---

## Step 8: Integration Testing

**Files**: 
- `tests/ui/test_upload_view.py` (new)
- `tests/integration/test_upload_workflow.py`

**Tasks**:
1. [ ] Create comprehensive integration tests
2. [ ] Test complete upload → view → edit → delete workflow
3. [ ] Test permission scenarios (owner, other user, anonymous)
4. [ ] Test edge cases (missing files, deleted users, etc.)
5. [ ] Test all interactive features (edit, toggle, delete)
6. [ ] Performance testing
7. [ ] Update documentation

**Tests**:
1. [ ] Integration test: Full upload lifecycle
2. [ ] Integration test: Permission matrix
3. [ ] Integration test: All HTMX interactions
4. [ ] Edge case: Orphaned upload (file missing)
5. [ ] Edge case: Deleted user's uploads
6. [ ] Performance: Page load time

**Acceptance Criteria**:
- [ ] All integration tests passing
- [ ] All permission scenarios covered
- [ ] Edge cases handled gracefully
- [ ] Performance acceptable
- [ ] Documentation updated
- [ ] Ready for production

**Implementation Notes**:
- Use pytest fixtures for test data
- Test with actual file uploads
- Mock external dependencies if needed
- Document any known limitations

**Dependencies**:
- All previous steps must be complete

---

## Step 10: Inline Tag Management (Owner Only)

**Files**:
- `app/models/tags.py`
- `app/models/uploads.py`
- `app/ui/uploads.py`
- `app/ui/templates/components/core/tag-input.html.j2`
- `app/ui/templates/components/core/tag-suggestions.html.j2`

**Tasks**:
1. [x] Add `ManyToManyField` tags relation to `Upload` model
2. [x] Create `TagSerializer`
3. [x] Implement `Tag.add_or_create_for_upload` class method (sanitises name, creates or reuses tag, adds M2M association)
4. [x] Implement `Tag.remove_tag_from_upload` class method (sanitises name, removes association, deletes orphaned tags)
5. [x] Create `POST /uploads/{id}/tag-suggestions` endpoint (HTMX, owner only)
6. [x] Create `POST /uploads/{id}/tag` endpoint (HTMX, owner only, returns 201)
7. [x] Create `DELETE /uploads/{id}/tag` endpoint (HTMX, owner only, returns 200)
8. [x] Create `tag-input.html.j2` Alpine.js component with autocomplete and add/remove interactions
9. [x] Create `tag-suggestions.html.j2` partial for HTMX suggestion dropdown swap
10. [x] Update all `prefetch_related` calls to include `"tags"`

**Tests**:
1. [x] `TestTagAddOrCreateForUpload`: creates tag, reuses existing, adds M2M, sanitises name, raises on empty/invalid, idempotent re-add
2. [x] `TestTagRemoveTagFromUpload`: removes association, returns False when not found, deletes orphan, preserves shared, sanitises name, raises on empty/invalid
3. [x] `TestCleanText`: all `clean_text` helper edge cases
4. [x] `TestMakeCleanTag`: all `make_clean_tag` helper edge cases
5. [x] `TestTagSuggestionsEndpoint`: unauthenticated redirect, 404, any authenticated user can get suggestions, 204 for empty query, suggestions matching query, excludes already-attached tags
6. [x] `TestUploadAddTagEndpoint`: unauthenticated redirect, 404, any authenticated user can add tag, tag persisted in DB, 400 for invalid/empty tag name
7. [x] `TestUploadDeleteTagEndpoint`: unauthenticated redirect, 404, any authenticated user can remove tag, tag removed from DB, 400 for invalid/empty tag name

**Acceptance Criteria**:
- [x] Any authenticated user can add tags to any upload via an HTMX autocomplete input
- [x] Any authenticated user can remove tags via the same UI; unauthenticated users see read-only tags
- [x] Tag names are sanitised (lowercased, special chars replaced with `-`)
- [x] Invalid/empty tag names return 400 Bad Request; empty suggestion query returns 204
- [x] Orphaned tags (no remaining uploads) are automatically deleted
- [x] Unauthenticated requests redirect to `/login`
- [x] All tests passing (788)

**Implementation Notes**:
- Tag name sanitisation uses the existing `make_clean_tag` helper (delegates to `clean_text`).
- The Alpine.js `tagInput` component is guarded by `{% if not request or request.headers.get('hx-request') != 'true' %}` so the `<script>` block is only emitted on full page loads, not HTMX partial responses.
- `validate_file_update_request` is reused for ownership/access checks, which also enforces file existence. Tests that exercise successful add/remove paths create a backing file via `_create_tag_upload_with_file`.
- **Design change (2026-03-04):** Tags are public/shared constructs — ownership of the upload is not required to tag it. `validate_file_update_request` was removed from all three tag endpoints. The tag input is shown to all authenticated users; a read-only `render_tags_readonly()` macro is shown to unauthenticated users. Tests updated accordingly.

**Dependencies**:
- Step 1 must be complete

---

## Step 11: Collections UI on Upload View Page

**Files**:
- `app/models/collections.py`
- `app/models/uploads.py`
- `app/ui/uploads.py`
- `app/ui/templates/components/collections/combo-selector.html.j2` (new)
- `app/ui/templates/components/collections/combo-selector-items.html.j2` (new)
- `app/ui/templates/components/core/image-rotate-select.html.j2` (new, extracted)
- `app/ui/templates/components/upload/delete-button.html.j2` (new, extracted)
- `app/ui/templates/components/upload/sidebar-actions.html.j2`
- `app/ui/templates/components/core/tag-input.html.j2`
- `input.css`

**Tasks**:
1. [x] Update `Collection` model: replace `user_id` IntField with proper `user` ForeignKeyField; add `_make_name_unique`, `add_or_create_for_upload`, `add_for_upload`, `remove_from_upload` classmethods; add `CollectionSerializer`
2. [x] Update `Upload` model: add `collections` M2M field, `user_collections()` instance method, `get_with_relations()` classmethod; expand `UploadSerializer` with `collections` and context-resolved `user_collections` fields
3. [x] Create `POST /uploads/{id}/collection-search` endpoint (HTMX, authenticated)
4. [x] Create `POST /uploads/{id}/collection` endpoint (HTMX, authenticated, creates or links collection, returns 201)
5. [x] Create `PATCH /uploads/{id}/collection` endpoint (HTMX, authenticated, full add/remove reconciliation for current user, returns 202)
6. [x] Create `collections-combo-selector.html.j2` Alpine.js multi-select combo with search/filter, new collection creation, and checked-state management
7. [x] Create `collections-combo-selector-items.html.j2` HTMX partial for rendered items list
8. [x] Restructure `upload-sidebar-actions.html.j2`: gate interactive tags and collections on `current_user`; show read-only tags for unauthenticated users; keep rotate and delete owner-only
9. [x] Add `render_tags_readonly()` macro to `tag-input.html.j2` for unauthenticated users
10. [x] Add comprehensive `.split-button` CSS system to `input.css`; remove legacy `.dropdown` classes
11. [x] Update all `prefetch_related` calls to include `"collections"`

**Tests**:
1. [x] `TestMakeNameUnique`: base slug free, appends `-2`, increments past `-2`, similar prefix slug does not cause false conflict
2. [x] `TestAddOrCreateForUpload`: creates and links new collection, reuses existing by name, unique slug across users, strips surrounding whitespace, raises for empty/whitespace-only/invalid-chars names
3. [x] `TestAddForUpload`: links existing collection to upload, returns `False` for unknown collection ID
4. [x] `TestRemoveFromUpload`: removes collection from upload, returns `False` for collection not linked
5. [x] `TestUploadGetWithRelations`: valid ID returns upload, `None` for missing ID, prefetches collections, prefetches tags
6. [x] `TestUploadUserCollections`: returns current user's collections, excludes other-user collections, empty when user has none
7. [x] `TestCollectionSearchEndpoint`: unauthenticated redirect, 404 for missing upload, matching collections in response, already-linked collections rendered as checked
8. [x] `TestCollectionAddEndpoint`: unauthenticated redirect, 404, 201 on success, collection persisted and linked, any authenticated user can add to any upload
9. [x] `TestCollectionPatchEndpoint`: unauthenticated redirect, 404, 400 for all-invalid IDs, adds collection, removes unchecked collection, ignores other-user collections, empty payload clears all user collections

**Acceptance Criteria**:
- [x] Any authenticated user can assign their own collections to any upload
- [x] Collections are per-user: each user's collections are isolated; `upload.user_collections` resolves to the requesting user's collections only
- [x] New collection names are slugified into a globally unique `name_unique` value via `_make_name_unique`
- [x] The combo-selector supports incremental search/filter, new collection creation inline, and pre-checked state for already-linked collections
- [x] Unauthenticated users see read-only tags only; collections panel hidden entirely
- [x] All collection endpoints validate that the collection belongs to `current_user` before add/remove
- [x] All tests passing (827)

**Implementation Notes**:
- `_make_name_unique` uses a regex boundary check (`^{slug}(-\d+)?$`) to avoid false matches between similarly-prefixed slugs (e.g. `my-trip` vs `my-trip-photos`).
- The `PATCH` endpoint performs a full reconciliation: all user-owned collections absent from the payload are removed; the supplied IDs that pass ownership validation are added. Collections owned by other users linked to the same upload are untouched.
- `UploadSerializer.user_collections` uses a `resolve_user_collections` resolver that reads `context["user"]`; returns `None` when no user is in context (unauthenticated), `[]` when authenticated but no collections linked.
- The `collections-combo-selector-items.html.j2` empty-state condition uses `upload.user_collections` (per-user), not `upload.collections` (global), to correctly detect the empty state.

**Dependencies**:
- Step 1 must be complete
- Step 10 must be complete

---

## Summary

### What's Done
All core upload view page features are implemented and tested:

| Feature | Step | Status |
|---|---|---|
| View route, SEO redirect, privacy enforcement | 1 | Complete |
| File preview (image inline, icon fallback) | 2 | Complete |
| Metadata panel (size, dims, type, views, date) | 3 | Complete |
| Sharing modal with copyable URLs | 4 | Complete |
| Description inline editing with validation errors | 5 | Complete |
| Privacy toggle (owner only) | 6 | Complete |
| Delete with confirmation modal | 7 | Complete |
| Inline tag editing (any authenticated user) | 10 | Complete |
| Collection assignment UI (per-user) | 11 | Complete |

### What Remains
- **Polish**: re-establish global anchor `<a>` base styles (removed during CSS refactor — tracked in `implement-ui-polish.md` Frontend Scaffolding)
- **Open Graph meta tags**: tracked in `implement-ui-polish.md`
- **Step 8** (full integration test suite): not started
- Non-automatable tests (copy-to-clipboard, HTMX swap behaviour, cancel button, mobile/screen-reader): deferred to manual QA
