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
- No individual upload view page exists
- Upload model has all necessary metadata fields
- Image model has dimension data for images
- Upload model has `url` property for file serving
- No UI for editing upload metadata
- No UI for privacy controls
- No delete functionality implemented
- Profile page shows list of user's uploads

### Target State
- `/view/{id}/{filename}` endpoint renders upload detail page
- File preview displayed appropriately based on type
- All metadata visible (size, dimensions, type, views, date)
- Copy-to-clipboard sharing links
- Inline edit form for title/description (HTMX-powered)
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
1. [ ] Create GET `/view/{id}` route (redirects to add filename)
2. [ ] Create GET `/view/{id}/{filename}` route (main view page)
3. [ ] Fetch upload from database with related data (images, user)
4. [ ] Validate upload exists (404 if not)
5. [ ] Get current user for permission checks
6. [ ] Enforce privacy: private uploads only accessible to owner (403 if not)
7. [ ] Create base template with layout
8. [ ] Pass upload data and permissions to template
9. [ ] Redirect `/view/{id}` to `/view/{id}/{cleanname}` with 301

**Tests**:
1. [ ] Test view page renders for existing public upload
2. [ ] Test 404 for non-existent upload
3. [ ] Test public upload accessible to anonymous users
4. [ ] Test public upload accessible to authenticated users
5. [ ] Test private upload accessible to owner
6. [ ] Test private upload returns 403 for other users
7. [ ] Test private upload returns 403 for anonymous users
8. [ ] Test redirect from `/view/{id}` to `/view/{id}/{filename}`
9. [ ] Test correct data passed to template

**Acceptance Criteria**:
- [ ] View page route functional
- [ ] Privacy enforced (private uploads owner-only)
- [ ] SEO-friendly URLs with filename
- [ ] Proper error handling (404, 403)
- [ ] All tests passing

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
1. [ ] Create file preview component
2. [ ] Display images inline with `<img>` tag
3. [ ] Display videos with `<video>` player
4. [ ] Display audio with `<audio>` player
5. [ ] Display file icon for other types
6. [ ] Add loading states and error handling
7. [ ] Make preview responsive

**Tests**:
1. [ ] Test image preview renders correctly
2. [ ] Test video preview with controls
3. [ ] Test audio preview with controls
4. [ ] Test generic file icon for documents
5. [ ] Test responsive sizing
6. [ ] Test broken image handling

**Acceptance Criteria**:
- [ ] Images display inline
- [ ] Videos playable in browser
- [ ] Audio playable in browser
- [ ] Other files show appropriate icon
- [ ] Responsive and accessible
- [ ] All tests passing

**Implementation Notes**:
- Use `upload.url` for file source
- Check `upload.type` (MIME type) to determine preview type
- For images, check `upload.is_image` property
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
1. [ ] Create metadata panel component
2. [ ] Display file size (formatted, e.g., "2.5 MB")
3. [ ] Display dimensions for images (width x height)
4. [ ] Display MIME type
5. [ ] Display view count
6. [ ] Display upload date (formatted)
7. [ ] Display uploader username
8. [ ] Display title and description
9. [ ] Style metadata panel

**Tests**:
1. [ ] Test all metadata fields display
2. [ ] Test file size formatting
3. [ ] Test dimension display for images
4. [ ] Test dimension not shown for non-images
5. [ ] Test date formatting
6. [ ] Test missing metadata handled gracefully

**Acceptance Criteria**:
- [ ] All metadata visible and formatted
- [ ] Clean, readable layout
- [ ] Responsive design
- [ ] All tests passing

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
- `app/ui/templates/uploads/view.html.j2`
- `app/ui/templates/uploads/components/share-panel.html.j2` (new)
- `app/static/js/share.js` (new, or use Alpine.js)

**Tasks**:
1. [ ] Create share panel component
2. [ ] Display direct link (view page URL)
3. [ ] Display file link (direct file URL with target=_blank)
4. [ ] Add copy-to-clipboard buttons for both links
5. [ ] Add visual feedback on copy (toast/notification)
6. [ ] Make links selectable for manual copy

**Tests**:
1. [ ] Test direct link displays correct view page URL
2. [ ] Test file link displays correct file URL
3. [ ] Test file link opens in new tab (target=_blank)
4. [ ] Test copy-to-clipboard functionality
5. [ ] Test visual feedback on copy
6. [ ] Test links are selectable
7. [ ] Test on mobile devices

**Acceptance Criteria**:
- [ ] Share links displayed correctly
- [ ] File link opens in new tab
- [ ] Copy-to-clipboard works
- [ ] Good user feedback
- [ ] Mobile-friendly
- [ ] All tests passing

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
1. [ ] Add edit form for description field
2. [ ] Show edit form only to upload owner
3. [ ] Create PATCH endpoint for updating upload description
4. [ ] Use HTMX for inline editing without page reload
5. [ ] Validate description (prevent injection attacks, max 255 chars)
6. [ ] Update upload.description in database
7. [ ] Return updated content to replace form
8. [ ] Add cancel button to revert changes

**Tests**:
1. [ ] Test edit form visible to owner
2. [ ] Test edit form hidden from non-owners
3. [ ] Test successful description update
4. [ ] Test validation prevents injection attacks
5. [ ] Test max length validation (255 chars)
6. [ ] Test HTMX swap behavior
7. [ ] Test cancel button
8. [ ] Test unauthorized edit attempt (403)

**Acceptance Criteria**:
- [ ] Owner can edit description inline
- [ ] Non-owners cannot see edit controls
- [ ] Updates work without page reload
- [ ] Proper validation and error handling
- [ ] All tests passing

**Implementation Notes**:
- Edit field: `upload.description` (max 255 chars, defaults to originalname.ext)
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
- `app/ui/templates/uploads/view.html.j2`
- `app/ui/templates/uploads/components/privacy-toggle.html.j2` (new)

**Tasks**:
1. [ ] Add privacy toggle switch (public/private)
2. [ ] Show toggle only to upload owner
3. [ ] Create POST endpoint for toggling privacy
4. [ ] Use HTMX for toggle without page reload
5. [ ] Update `private` field in database (0 or 1)
6. [ ] Return updated toggle state
7. [ ] Show visual feedback on change

**Tests**:
1. [ ] Test toggle visible to owner
2. [ ] Test toggle hidden from non-owners
3. [ ] Test toggle from public to private
4. [ ] Test toggle from private to public
5. [ ] Test HTMX behavior
6. [ ] Test unauthorized toggle attempt (403)
7. [ ] Test database update

**Acceptance Criteria**:
- [ ] Owner can toggle privacy inline
- [ ] Non-owners cannot see toggle
- [ ] Updates work without page reload
- [ ] Database updated correctly
- [ ] All tests passing

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
- `app/ui/templates/uploads/view.html.j2`
- `app/ui/templates/uploads/components/delete-modal.html.j2` (new)
- `app/lib/upload_handler.py` (if needed)

**Tasks**:
1. [ ] Add delete button (owner only)
2. [ ] Create HTMX-powered confirmation modal
3. [ ] Create DELETE endpoint for upload
4. [ ] Verify user is owner before allowing delete
5. [ ] Delete file from filesystem (hard delete)
6. [ ] Delete upload record from database
7. [ ] Delete related image records (cascade)
8. [ ] Redirect to profile after delete
9. [ ] Handle errors gracefully (file missing, etc.)

**Tests**:
1. [ ] Test delete button visible to owner
2. [ ] Test delete button hidden from non-owners
3. [ ] Test confirmation modal displays
4. [ ] Test successful deletion (file + database)
5. [ ] Test file removed from filesystem
6. [ ] Test database record removed
7. [ ] Test related image records removed (cascade)
8. [ ] Test unauthorized delete attempt (403)
9. [ ] Test delete non-existent upload (404)
10. [ ] Test delete with missing file (handles gracefully)

**Acceptance Criteria**:
- [ ] Owner can delete their uploads
- [ ] Confirmation required before delete
- [ ] File and database records permanently removed (hard delete)
- [ ] Proper error handling
- [ ] All tests passing

**Implementation Notes**:
- Endpoint: `DELETE /uploads/{id}`
- Use HTMX-powered modal for confirmation
- Hard delete: permanently remove file and database record
- Delete file using `upload.filepath.unlink(missing_ok=True)`
- Delete database record (cascades to images table via foreign key)
- Check `current_user.id == upload.user_id` before allowing delete
- Redirect to `/profile` after successful delete
- Admin delete functionality is out of scope (future enhancement)

**Dependencies**:
- Step 1 must be complete

---

## Step 8: Polish and Accessibility

**Files**: 
- `app/ui/templates/uploads/view.html.j2`
- All component templates

**Tasks**:
1. [ ] Add breadcrumb navigation
2. [ ] Add "Back to uploads" link
3. [ ] Ensure keyboard navigation works
4. [ ] Add ARIA labels for accessibility
5. [ ] Test with screen readers
6. [ ] Optimize page load performance
7. [ ] Add meta tags for social sharing (Open Graph)
8. [ ] Mobile responsive testing

**Tests**:
1. [ ] Test breadcrumb navigation
2. [ ] Test keyboard navigation
3. [ ] Test screen reader compatibility
4. [ ] Test mobile responsiveness
5. [ ] Test page load performance
6. [ ] Test social sharing preview

**Acceptance Criteria**:
- [ ] Fully accessible (WCAG 2.1 AA)
- [ ] Keyboard navigable
- [ ] Mobile responsive
- [ ] Fast page load
- [ ] Good social sharing preview
- [ ] All tests passing

**Implementation Notes**:
- Breadcrumb: Home → Uploads → [Upload Title]
- Add `<meta>` tags for Open Graph (og:image, og:title, etc.)
- Use semantic HTML elements
- Test with Lighthouse for accessibility and performance
- Consider lazy loading for images

**Dependencies**:
- All previous steps must be complete

---

## Step 9: Integration Testing

**Files**: 
- `tests/ui/test_upload_view.py` (new)
- `tests/integration/test_upload_workflow.py`

**Tasks**:
1. [ ] Create comprehensive integration tests
2. [ ] Test complete upload → view → edit → delete workflow
3. [ ] Test permission scenarios (owner, other user, anonymous, admin)
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
