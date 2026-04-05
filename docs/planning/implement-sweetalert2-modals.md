# Implementation Plan: SweetAlert2 Modal Refactor

## Overview

Replace all custom Alpine.js-powered modals and flash message popups with SweetAlert2, eliminating bespoke modal code and its associated debugging overhead.

### Scope
- Delete confirmation dialogs (single upload and gallery bulk)
- Share URL modal
- Flash message notifications
- Removal of unused modal macro templates

### Current State
- Custom modal macros: `modal-basic.html.j2`, `modal-dialog.html.j2`
- Alpine.js `x-data="{ open: false }"` pattern used in delete and share button components
- Flash messages rendered server-side via Alpine.js-driven `#messages` div with HTMX OOB swap
- SweetAlert2 is not installed

### Target State
- SweetAlert2 installed as a local vendor script
- Delete confirmations use `Swal.fire()` confirm dialogs
- Share URL display uses `Swal.fire()` with HTML content
- Flash messages use SweetAlert2 toast notifications
- `modal-basic.html.j2` and `modal-dialog.html.j2` deleted
- Image preview modal (`view-modal.html.j2`) remains unchanged

---

## Step 1: Install SweetAlert2

**Files**:
- `app/static/js/vendor/sweetalert2.all.min.js` (new)
- `app/ui/templates/layout/header-includes.html.j2`

**Tasks**:
1. [x] Download `sweetalert2.all.min.js` (combined JS+CSS bundle) from the SweetAlert2 release and place in `app/static/js/vendor/`
2. [x] Add script tag to `header-includes.html.j2` before the Alpine.js script tag

**Tests**:
1. [x] `Swal.fire('test')` is callable from browser console on any page without errors

**Acceptance Criteria**:
- [x] SweetAlert2 loads on all pages
- [x] No conflicts with Alpine.js or HTMX

---

## Step 2: Replace Single-Upload Delete Confirmation

**Files**:
- `app/ui/templates/components/uploads/delete-button.html.j2`

**Tasks**:
1. [x] Remove the `{% from "components/core/modal-dialog.html.j2" import render_dialog %}` import
2. [x] Remove the `x-data="{ open: false }"` outer wrapper
3. [x] Remove the `{% call render_dialog(...) %}` block and its inner buttons
4. [x] Change the Delete button click handler to open a SweetAlert2 confirm dialog, then trigger the HTMX delete request on confirmation

**Tests**:
1. [x] Clicking Delete opens the SweetAlert2 dialog
2. [x] Clicking Cancel in the dialog dismisses it without any request
3. [x] Clicking Delete in the dialog sends the HTMX delete request

**Acceptance Criteria**:
- [x] No references to `modal-dialog.html.j2` or `x-data="{ open: false }"` remain in this file
- [x] Upload is deleted on confirmation

**Implementation Notes**:
- A reusable `sweetConfirm(el, config)` helper was added to `app/static/js/app/lib/helpers.js`; it calls `Swal.fire(config)` and dispatches a `confirmed` event on the element if the user confirms
- The Delete button uses `hx-trigger="confirmed"` and `hx-delete` directly, with `@click="sweetConfirm($el, {...})"` — cleaner than calling `htmx.ajax()` manually and more idiomatic HTMX; `sweetConfirm` is reusable for subsequent steps
- No `hx-target`/`hx-swap` needed: the server issues an `HX-Redirect` on success; the redirect URL is passed as a query param via `hx-vals`, set to the page's `Referer` header at render time (falling back to the index page), so the user is returned to wherever they came from

---

## Step 3: Replace Gallery Bulk Delete Confirmation

**Files**:
- `app/ui/templates/components/gallery/delete-button.html.j2`

**Tasks**:
1. [x] Remove the `{% from "components/core/modal-dialog.html.j2" import render_dialog %}` import
2. [x] Remove the `{% call render_dialog(...) %}` block
3. [x] Apply the same `sweetConfirm` + `hx-trigger="confirmed"` pattern as Step 2, with `redirect` passed via `hx-vals` as a `Form()` parameter
4. [x] Add `id="multiselect-chrome"` and `@clear-selection="clearSelection()"` to the multiselect chrome div; server fires `clear-selection` via `HX-Trigger` on success

**Tests**:
1. [x] Clicking Delete opens the SweetAlert2 dialog
2. [x] Clicking Cancel dismisses the dialog without any request
3. [x] Clicking Delete in the dialog posts with correct `hx-include` form values collected
4. [x] `clearSelection()` is called after the deletion completes

**Acceptance Criteria**:
- [x] Selected uploads are deleted on confirmation
- [x] Selection is cleared after deletion
- [x] `hx-include` form value collection still works

**Implementation Notes**:
- Same `sweetConfirm` helper used as Step 2; confirmation text is dynamic using `selectedCount`
- `redirect` is a `Form()` parameter (POST endpoint), passed via `hx-vals` alongside `hx-include` fields
- Selection is cleared via a `clear-selection` HTMX event fired server-side in `HX-Trigger`, handled by `@clear-selection="clearSelection()"` on `#multiselect-chrome`
- The gallery delete button is also included in `multiselect-sidebar-actions.html.j2`, enabling bulk delete from the sidebar

**Dependencies**:
- Step 1

---

## Step 4: Replace Share Modal

**Files**:
- `app/ui/templates/components/uploads/share-button.html.j2`

**Tasks**:
1. [ ] Remove the `{% from "components/core/modal-basic.html.j2" import render_modal with context %}` import
2. [ ] Remove the `x-data="{ open: false }"` wrapper and `{% call render_modal(...) %}` block
3. [ ] Change the share button click handler to call `Swal.fire({ title: 'Share upload', html: '...', showConfirmButton: false, showCloseButton: true })`
4. [ ] Move the URL inputs and copy buttons into the `html` string value, pre-rendered via Jinja2
5. [ ] Replace Alpine `$clipboard(value)` calls with `navigator.clipboard.writeText(value)` in copy button `onclick` handlers

**Tests**:
1. [ ] Clicking Share opens the SweetAlert2 dialog with the correct URLs
2. [ ] Clicking a copy button copies the URL to clipboard
3. [ ] Private upload shows "This upload is private" message instead of URLs
4. [ ] Modal closes with the X button

**Acceptance Criteria**:
- [ ] No references to `modal-basic.html.j2` or `$clipboard` remain in this file
- [ ] All three URL types displayed for public image uploads
- [ ] Clipboard copy works without Alpine.js magic

**Implementation Notes**:
- Jinja2 conditionals (`{% if not upload.is_private %}`, `{% if upload.is_image %}`) are evaluated server-side and rendered into the `html` string before it reaches the browser
- Alpine.js magic properties do not function inside SweetAlert2's dynamically injected HTML

**Dependencies**:
- Step 1

---

## Step 5: Replace Flash Messages with SweetAlert2 Toasts

**Files**:
- `app/ui/templates/components/core/messages.html.j2`

**Tasks**:
1. [ ] Replace the Alpine.js-driven message lists with a `<script>` block that calls `Swal.fire({ toast: true, ... })` for each message in each severity category
2. [ ] Keep an empty `<div id="messages" hx-swap-oob="outerHTML:#messages"></div>` so HTMX OOB swaps continue to work and trigger new toasts
3. [ ] Map severity types: `info` → `icon: 'success'`, `warning` → `icon: 'warning'`, `error` → `icon: 'error'`
4. [ ] Pass `{{ message | markdown | safe }}` as the `html` parameter (not `title`) to preserve markdown rendering

**Tests**:
1. [ ] Flash messages from initial page load appear as toasts in the top-right corner
2. [ ] Messages returned via HTMX OOB swap also appear as toasts
3. [ ] Info, warning, and error messages each show with their correct icons
4. [ ] Toasts auto-dismiss after a few seconds

**Acceptance Criteria**:
- [ ] All Alpine.js message-related state removed from this template
- [ ] Toasts appear for all three severity levels
- [ ] HTMX OOB swap mechanism still works (new messages after HTMX actions show as toasts)

**Implementation Notes**:
- SweetAlert2 config: `position: 'top-end'`, `timer: 4000`, `timerProgressBar: true`, `showConfirmButton: false`
- Multiple toasts stack correctly in SweetAlert2 without extra configuration

**Dependencies**:
- Step 1

---

## Step 6: Remove Unused Modal Macros

**Files**:
- `app/ui/templates/components/core/modal-basic.html.j2` (delete)
- `app/ui/templates/components/core/modal-dialog.html.j2` (delete)

**Tasks**:
1. [ ] Verify no remaining `{% from "components/core/modal-basic.html.j2" %}` imports exist in any template
2. [ ] Verify no remaining `{% from "components/core/modal-dialog.html.j2" %}` imports exist in any template
3. [ ] Delete `modal-basic.html.j2`
4. [ ] Delete `modal-dialog.html.j2`

**Tests**:
1. [ ] Application starts without Jinja2 template import errors

**Acceptance Criteria**:
- [ ] Both macro files are deleted
- [ ] No templates reference either file

**Dependencies**:
- Steps 2, 3, 4
