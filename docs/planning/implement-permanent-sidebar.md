# Implementation Plan: Permanent Per-View Sidebar Widgets

## Overview

Extend the gallery sidebar to support permanent, per-view widget areas alongside the existing multiselect sidebar. Each view (collection, tag, etc.) can inject its own contextual detail widget above the multiselect sidebar. Initial implementation adds collection and tag detail sidebars, a collection delete action, and a multi-format archive download refactor.

### Scope
- `gallery_sidebar_widgets` Jinja2 block for per-view sidebar widget injection
- Collection view sidebar: stats, multi-format download button, owner-only delete
- Tag view page and sidebar: stats and download button
- `DELETE /collections/{id}` endpoint with same-origin redirect
- Archive download button refactored to multi-format with per-format inline status

### Current State
- All steps complete; 57/57 archive tests passing
- Sidebar-specific tests still outstanding (see Step 3)

### Target State
- Each gallery-derived view can inject a permanent detail widget into the sidebar
- Collection sidebar shows owners, file types, file size, multi-format download, and delete
- Tag sidebar shows owners, file types, file size, and multi-format download
- Archive download button supports all formats with inline pending/processing status per format

---

## Step 1: Gallery Sidebar Widget Block

**Files**:
- `app/ui/templates/gallery/index.html.j2`
- `app/ui/templates/gallery/partials/sidebar.html.j2`

**Tasks**:
1. [x] Add `{% block gallery_sidebar_widgets %}{% endblock %}` to the gallery sidebar, positioned above the multiselect sidebar
2. [x] Verify block renders correctly and does not affect existing multiselect sidebar behaviour

**Tests**:
1. [x] Existing multiselect sidebar tests unaffected (57/57 passing)

**Acceptance Criteria**:
- [x] Child templates can inject widgets above the multiselect sidebar via the block
- [x] No regression in existing sidebar behaviour

---

## Step 2: Collection View Sidebar

**Files**:
- `app/ui/templates/collections/partials/sidebar-details.html.j2`
- `app/ui/templates/collections/partials/sidebar.html.j2`
- `app/ui/collections.py`
- `app/ui/common/archives.py`

**Tasks**:
1. [x] Update `sidebar-details.html.j2` to display collection stats (owners, file types, file size) when uploads exist (`collection.selection_detail.upload_count`)
2. [x] Add multi-format download button via `multiselect_download_button` macro when uploads exist
3. [x] Add owner-only delete button (`collection.user.id == current_user.id`) with SweetAlert2 confirmation
4. [x] Pass `download_archives` context to the collection view
5. [x] Implement `DELETE /collections/{id}` with `get_or_none(id=id, user=current_user)` ownership check, `logger.exception` on error, flash on success, and same-origin redirect via `urllib.parse.urlunparse`

**Tests**:
1. [ ] Collection sidebar renders stats correctly for a collection with uploads
2. [ ] Collection sidebar shows delete button for owner, not for other authenticated users
3. [ ] `DELETE /collections/{id}` returns 400 for non-existent or unowned collection
4. [ ] `DELETE /collections/{id}` redirects to index when no redirect param provided
5. [ ] `DELETE /collections/{id}` strips host from redirect param (open-redirect prevention)

**Acceptance Criteria**:
- [x] Stats, download button, and delete visible in collection sidebar
- [x] Delete guarded by ownership check at both template and endpoint level
- [x] Open redirect prevented by stripping host from redirect URL
- [ ] Tests written and passing

**Implementation Notes**:
- `redirect` query param typed as `str | None`; host is stripped via `parse.urlunparse((request.url.scheme, request.url.netloc, parsed.path, parsed.params, parsed.query, parsed.fragment))`
- `hx-delete` uses `request.url_for('delete_collection_delete', id=collection.id)` — no hardcoded paths
- `hx-vals` passes `redirect` sourced from the `Referer` header; sanitised server-side

---

## Step 3: Tag View Page and Sidebar

**Files**:
- `app/ui/templates/tags/view.html.j2`
- `app/ui/templates/tags/partials/sidebar-details.html.j2`
- `app/ui/templates/tags/partials/sidebar.html.j2`
- `app/ui/tags.py`
- `app/ui/archives.py`

**Tasks**:
1. [x] Create `tags/view.html.j2` extending `gallery/index.html.j2`, injecting the tag sidebar via `gallery_sidebar_widgets`
2. [x] Create `tags/partials/sidebar-details.html.j2` displaying tag stats and multi-format download button for authenticated users
3. [x] Update `tags_view_get` to pass `tag` and `download_archives` context; switch template to `tags/view.html.j2`
4. [x] Implement tag branch in `request_uploads_archive_post`: `Tag.get_or_none(name=tag_slug)` with auth check, `context_filter = Q(tags__id=tag_model.id)`, `super_selected = True`

**Tests**:
1. [ ] Tag sidebar renders stats correctly for an authenticated user
2. [ ] Tag sidebar download button not shown for anonymous users
3. [ ] Archive request from tag view correctly scopes uploads to the tag

**Acceptance Criteria**:
- [x] Tag view uses tag-specific template with sidebar widget
- [x] Sidebar shows stats and download button for authenticated users
- [ ] Tests written and passing

**Implementation Notes**:
- Tags are not user-owned; the archive endpoint checks `current_user.is_authenticated` rather than ownership; upload-level read access is still enforced downstream by `get_readable_selected_upload_models`
- `tag.id` in `hx_vals` is passed to the endpoint but unused server-side; the tag is identified from the URL path

---

## Step 4: Multi-Format Archive Download Refactor

**Files**:
- `app/ui/templates/components/gallery/download-button.html.j2`
- `app/ui/templates/components/gallery/macro_download-button-format-item.html.j2`
- `app/ui/templates/components/gallery/macro_download-button.html.j2`
- `app/ui/common/archives.py`
- `app/ui/common/gallery.py`
- `app/ui/archives.py`

**Tasks**:
1. [x] Extract `get_selected_uploads_archives` to `app/ui/common/archives.py`; returns most-recent non-failed archive per format
2. [x] Refactor `download-button.html.j2` to show pending/processing inline status with polling for the ZIP primary action; ready state shows download link; no-archive/failed shows request button
3. [x] Refactor `macro_download-button-format-item.html.j2` to show per-format pending/processing/ready/request states in the dropdown
4. [x] Update `request_uploads_archive_post` to dispatch on `hx-target` header for collection and tag context-scoped archive requests
5. [x] Pass `download_button_name` (from `hx-target` header) to all `components/archives/download-button.html.j2` render sites

**Tests**:
1. [x] No existing archive → request button rendered (57/57 archive tests passing)
2. [x] Pending archive → status component with archive ID and "queued" text rendered
3. [x] Processing archive → status component with archive ID and "processing" text rendered
4. [x] Ready archive → download link rendered
5. [x] Failed archive excluded → request button rendered

**Acceptance Criteria**:
- [x] All four archive formats available via dropdown
- [x] Pending/processing archives show inline status without replacing the full button
- [x] Per-format dropdown items independently reflect their archive state
- [x] 57/57 archive tests passing

**Implementation Notes**:
- `get_selected_uploads_archives` orders by `format, -created_at` and deduplicates by format — callers always get the most recent archive per format
- Pending/processing state in `download-button.html.j2` polls `update_archive_status_get`; on completion HTMX replaces `#{{ button_id }}` with `components/archives/download-button.html.j2` (single-archive status template), which continues its own polling loop
- The `hx-target` header carries the button ID (without `#`) and doubles as the `download_button_name` for the archives status template
