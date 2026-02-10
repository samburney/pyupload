# Implementation Plan: Home Gallery Page

## Overview

Implement a home/landing page that displays a gallery of the latest public uploads, providing discovery and browsing functionality similar to simplegallery's main page.

### Scope
- Home page at `/` displaying latest public uploads
- Grid/gallery layout with thumbnails
- Pagination for browsing through uploads (24 items per page)
- Filter to show only public uploads (private=0)
- Responsive design for mobile and desktop (4x6, 3x8, 2x12 grids)
- Link to individual upload view pages
- Basic upload metadata display (description/filename, views, uploader)
- Empty state with upload CTA (works for all users via auto-account creation)

### Current State
- Home route fetches public uploads and owner's private uploads (Step 1 complete)
- Gallery grid renders with CSS multi-column layout (Step 2 partial)
- Pagination component reused and working (Step 4 complete)
- Empty state component created (Step 6 complete)
- Database index migration created for `private` column (Step 7 partial)
- `UploadSerializer`, `UserSerializer`, `ImageSerializer` added via `tortoise-serializer`
- `PaginationParams` enhanced with `count`, `pages`, `page_data()`
- `humanize_bytes` helper and Jinja filter added
- Base layout refactored with semantic HTML (`<nav>`, `<main>`, `<footer>`)
- 35 new tests passing (615 total)

### Target State
- ~~Home page displays grid of latest public uploads~~ ✅
- ~~Only public uploads (private=0) shown~~ ✅ (also includes owner's private uploads when logged in)
- ~~Pagination working with page controls~~ ✅
- ~~Responsive grid layout (1-4 columns based on screen size)~~ ✅
- Each upload shows thumbnail, title, view count — **view count not yet displayed**
- Click on upload navigates to view page — **image cards not yet linked**
- ~~Clean, modern design matching site theme~~ ✅
- Fast page load with optimized queries — **partial** (index added, no caching headers)
- ~~All tests passing~~ ✅
- Remaining: extract reusable card/grid components, add hover effects, link image cards, display view count, add relative date

---

## Step 1: Update Home Route with Upload Query

**Files**: 
- `app/ui/main.py`
- `app/models/uploads.py` (if needed)

**Tasks**:
1. [x] Update home route to fetch public uploads
2. [x] Filter for public uploads only (private=0) - also including owned, private uploads if logged in
3. [x] Order by created_at descending (newest first)
4. [x] Add pagination support
5. [x] Prefetch related data (images, user)
6. [x] Pass uploads and pagination data to template
7. [x] Handle empty state (no uploads)

**Tests**:
1. [x] Test home route returns public uploads only
2. [x] Test private uploads excluded
3. [x] Test uploads ordered by newest first
4. [x] Test pagination works
5. [x] Test related data prefetched
6. [x] Test empty state handled

**Acceptance Criteria**:
- [x] Home route fetches correct uploads
- [x] Only public uploads returned (plus owner's private uploads when logged in — exceeds plan)
- [x] Pagination functional
- [x] Efficient database queries
- [x] All tests passing (35 tests in `test_ui_home_gallery.py`)

**Implementation Notes**:
- Query: `Upload.filter(private=0).order_by('-created_at').prefetch_related('images', 'user')`
- Use `PaginationParams` dependency for pagination
- Page size: 24 uploads (works well with 4x6, 3x8, 2x12 grid layouts)
- Add database index via migration: `CREATE INDEX idx_uploads_private_created ON uploads(private, created_at DESC)`
- Handle case where no public uploads exist yet

**Deviation Notes** (reviewed 2026-02-10):
- Uses `Q(private=False) | Q(user=current_user)` to also show logged-in user's private uploads. This exceeds the plan's intent and is a good UX improvement.
- Uses `UploadSerializer` (via `tortoise-serializer`) instead of passing ORM models directly to templates.  This is a good architectural decision for clean data flow.
- `HomePaginationParams` subclass provides default sort/page_size.  Clean approach.
- Database index migration adds index on `private` column only (not composite `(private, created_at DESC)` as noted).  Still functional.

---

## Step 2: Create Gallery Grid Component

**Files**: 
- `app/ui/templates/index.html.j2`
- `app/ui/templates/components/upload-grid.html.j2` (new)
- `app/ui/templates/components/upload-card.html.j2` (new)

**Tasks**:
1. [ ] Create reusable upload grid component — *currently inline in `index.html.j2`, not extracted*
2. [ ] Create upload card component for individual items — *currently inline in `index.html.j2`, not extracted*
3. [x] Implement responsive grid layout (CSS Grid or Tailwind) — *uses CSS multi-column layout (`columns-*`)*
4. [x] Display upload thumbnail/preview
5. [x] Display upload title (or filename if no title) — *displays `upload.description`*
6. [ ] Display view count — **not yet displayed**
7. [x] Display uploader username
8. [ ] Link card to upload view page — **image cards are not linked, only non-image file icons are**
9. [ ] Add hover effects — **not yet implemented**

**Tests**:
1. [ ] Test grid renders with uploads
2. [ ] Test grid responsive at different breakpoints
3. [ ] Test card displays all metadata
4. [ ] Test card links to correct view page
5. [ ] Test hover effects work
6. [ ] Test empty grid state

**Acceptance Criteria**:
- [ ] Grid displays uploads in clean layout
- [ ] Responsive design works on all screen sizes
- [ ] All metadata visible
- [ ] Links functional
- [ ] All tests passing

**Implementation Notes**:
- Use Tailwind CSS grid: `grid grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-4`
- Grid layouts: 4x6 (desktop), 3x8 (tablet), 2x12 (mobile) for 24 items
- For thumbnails, use `upload.url` (will need thumbnail generation in future)
- For now, show full image or file icon
- Card should be clickable, linking to `/view/{upload.id}/{upload.cleanname}`
- Consider lazy loading images for performance
- Add loading skeleton for better UX

**Dependencies**:
- Step 1 must be complete

---

## Step 3: Implement Thumbnail Display

**Files**: 
- `app/ui/templates/components/upload-card.html.j2`
- `app/static/css/` (if custom CSS needed)

**Tasks**:
1. [ ] Display image thumbnails for image uploads
2. [ ] Display video icon/placeholder for videos
3. [ ] Display file icon for other file types
4. [ ] Implement aspect ratio container (e.g., 16:9 or 1:1)
5. [ ] Add loading states for images
6. [ ] Handle broken/missing images
7. [ ] Optimize image display (object-fit)

**Tests**:
1. [ ] Test image thumbnails display
2. [ ] Test video placeholders display
3. [ ] Test file icons display
4. [ ] Test aspect ratio maintained
5. [ ] Test broken image handling
6. [ ] Test loading states

**Acceptance Criteria**:
- [ ] Images display correctly
- [ ] Non-images show appropriate icons
- [ ] Consistent aspect ratios
- [ ] Good loading experience
- [ ] All tests passing

**Implementation Notes**:
- For images: `<img src="{{ upload.url }}" class="object-cover w-full h-full">`
- For now, use full image (thumbnail generation is future enhancement)
- Use `upload.is_image` to check if upload has image metadata
- Consider using placeholder images from a service or local assets
- Add `loading="lazy"` for performance
- Use Tailwind's `aspect-w-16 aspect-h-9` or similar for aspect ratio

**Dependencies**:
- Step 2 must be complete

---

## Step 4: Add Pagination Controls

**Files**: 
- `app/ui/templates/index.html.j2`
- `app/ui/templates/components/pagination.html.j2` (new, or reuse from profile)

**Tasks**:
1. [x] Create pagination component (or reuse existing) — *reused and updated existing component*
2. [x] Display page numbers
3. [x] Add previous/next buttons
4. [x] Show current page indicator
5. [x] Calculate total pages — *via `PaginationParams.pages` property*
6. [x] Generate page links with query parameters
7. [x] Handle edge cases (first page, last page)
8. [x] Make mobile-friendly

**Tests**:
1. [x] Test pagination displays correctly
2. [x] Test page links work
3. [x] Test previous/next buttons
4. [x] Test first page (no previous)
5. [x] Test last page (no next)
6. [x] Test middle pages
7. [ ] Test mobile display

**Acceptance Criteria**:
- [x] Pagination functional
- [x] All page navigation works
- [x] Edge cases handled
- [x] Mobile responsive
- [x] All tests passing

**Implementation Notes**:
- Reuse existing pagination component: `app/ui/templates/components/pagination.html.j2`
- Component expects `pagination` object with `.page` and `.pages` attributes
- Use query parameter: `?page=2`
- Component already handles: previous/next buttons, page numbers, disabled states
- Already mobile-friendly with Tailwind styling

**Dependencies**:
- Step 1 must be complete
- Step 2 must be complete

---

## Step 5: Add Metadata and Polish

**Files**: 
- `app/ui/templates/components/upload-card.html.j2`
- `app/ui/templates/index.html.j2`

**Tasks**:
1. [ ] Add upload title display (with fallback to filename)
2. [ ] Add view count display
3. [ ] Add uploader username display
4. [ ] Add upload date (relative time)
5. [ ] Add file type indicator
6. [ ] Style metadata for readability
7. [ ] Add tooltips for truncated text
8. [ ] Implement text truncation for long titles

**Tests**:
1. [ ] Test title displays correctly
2. [ ] Test fallback to filename
3. [ ] Test view count displays
4. [ ] Test username displays
5. [ ] Test date formatting
6. [ ] Test text truncation
7. [ ] Test tooltips

**Acceptance Criteria**:
- [ ] All metadata visible and formatted
- [ ] Truncation works for long text
- [ ] Clean, readable design
- [ ] All tests passing

**Implementation Notes**:
- Title: `{{ upload.description or upload.originalname }}` (description if set, else original filename)
- View count: `{{ upload.viewed }} views`
- Username: `{{ upload.user.username }}`
- Date: Use relative time (e.g., "2 hours ago") or format with Jinja filter
- Truncate with CSS: `truncate` class or `text-overflow: ellipsis`
- Add `title` attribute for full text on hover

**Dependencies**:
- Step 2 must be complete
- Step 3 must be complete

---

## Step 6: Add Empty State and Loading States

**Files**: 
- `app/ui/templates/index.html.j2`
- `app/ui/templates/components/empty-state.html.j2` (new)

**Tasks**:
1. [x] Create empty state component — `components/empty-content.html.j2` with SVG illustration
2. [x] Display message when no uploads exist
3. [x] Add CTA button linking to upload page — Upload + Home buttons included
4. [ ] Add loading skeleton for initial page load
5. [ ] Add loading states for pagination
6. [x] Style empty state attractively

**Tests**:
1. [x] Test empty state displays when no uploads
2. [x] Test empty state hidden when uploads exist
3. [ ] Test loading skeleton displays
4. [x] Test CTA button links to /upload
5. [ ] Test loading states for pagination

**Acceptance Criteria**:
- [x] Empty state displays correctly
- [ ] Loading states improve UX
- [x] CTA functional
- [x] All tests passing

**Implementation Notes**:
- Message: "No uploads yet. Be the first to upload!"
- CTA button links to `/upload` (works for all users - anonymous get auto-account via fingerprinting)
- Loading skeleton: Use Tailwind's animate-pulse
- Consider using HTMX indicators for loading states
- Only show empty state if `uploads|length == 0`
- Note: Anonymous users can upload (auto-account creation documented in docs/overview.md)

**Dependencies**:
- Step 2 must be complete

---

## Step 7: Optimize Performance

**Files**: 
- `app/ui/main.py`
- `app/models/uploads.py`

**Tasks**:
1. [ ] Create database migration for index
2. [ ] Optimize image loading (lazy loading)
3. [ ] Minimize database queries (N+1 prevention)
4. [ ] Add page caching headers
5. [ ] Profile page load performance
6. [ ] Optimize for mobile networks

**Tests**:
1. [ ] Test query performance with large dataset
2. [ ] Test N+1 query prevention
3. [ ] Test page load time
4. [ ] Test mobile performance
5. [ ] Test caching behavior

**Acceptance Criteria**:
- [ ] Page loads in < 2 seconds
- [ ] Efficient database queries
- [ ] No N+1 query issues
- [ ] Good mobile performance
- [ ] All tests passing

**Implementation Notes**:
- Create Aerich migration: `CREATE INDEX idx_uploads_private_created ON uploads(private, created_at DESC)`
- Use `.prefetch_related()` to avoid N+1 queries (already in Step 1)
- Add `Cache-Control` headers for static assets
- Use `loading="lazy"` on images
- Consider implementing Redis caching for popular pages (future enhancement)
- Profile with FastAPI profiling tools or browser DevTools

**Dependencies**:
- All previous steps should be complete

---

## Step 8: Integration Testing and Documentation

**Files**: 
- `tests/ui/test_home_page.py` (new)
- `tests/integration/test_gallery.py` (new)
- `README.md`

**Tasks**:
1. [ ] Create comprehensive integration tests
2. [ ] Test full browsing workflow
3. [ ] Test with various data scenarios (empty, few, many uploads)
4. [ ] Test responsive design at all breakpoints
5. [ ] Test accessibility (keyboard navigation, screen readers)
6. [ ] Performance testing with large datasets
7. [ ] Update documentation

**Tests**:
1. [ ] Integration test: Browse gallery → View upload
2. [ ] Integration test: Pagination workflow
3. [ ] Test with 0 uploads
4. [ ] Test with 100+ uploads
5. [ ] Test responsive breakpoints
6. [ ] Test accessibility compliance
7. [ ] Test page load performance

**Acceptance Criteria**:
- [ ] All integration tests passing
- [ ] Works with all data scenarios
- [ ] Fully responsive
- [ ] Accessible (WCAG 2.1 AA)
- [ ] Good performance
- [ ] Documentation updated
- [ ] Ready for production

**Implementation Notes**:
- Use pytest fixtures for test data
- Test with realistic data volumes
- Use Lighthouse for accessibility and performance audits
- Document any known limitations
- Add screenshots to documentation

**Dependencies**:
- All previous steps must be complete

---

## Potential Issues Identified

The following issues were identified during the branch review (2026-02-10).  These should be addressed before merging or in a follow-up.

### Bug: `UserSerializer.last_seen_at` typed as non-optional

**File**: `app/models/users.py` (line 124)

`last_seen_at` is typed as `datetime` in `UserSerializer`, but the database field is `DatetimeField(null=True)`.  When a user has never logged in (e.g. freshly created), serialisation fails with a Pydantic validation error.  The same issue may apply to `last_login_ip` (line 123) which is also `null=True` in the model but typed as `str`.

**Fix**: Change `UserSerializer` to:
- `last_seen_at: Optional[datetime]`
- `last_login_ip: Optional[str]`

**Workaround in tests**: `test_ui_home_gallery.py` uses a `_create_user()` helper that always provides `last_seen_at` to avoid this serialisation failure.  **Once the bug is fixed, remove the workaround** and verify tests still pass without setting `last_seen_at` explicitly.

### Bug: `PaginationMixin.paginate()` double-applies offset/limit/order

**File**: `app/models/common/pagination.py` (lines 58-62)

When a `query` argument is provided, the method builds an initial queryset with `.offset().limit().order_by()`, then calls `.filter(query).offset().limit().order_by()` again on top of that.  This redundantly applies the same clauses.  While it appears to produce correct results in SQLite testing, it could cause unexpected behaviour with other database backends.

**Fix**: Apply offset/limit/order_by only once, after all filters are composed:
```python
qs = cls.filter(*args, **kwargs)
if query:
    qs = qs.filter(query)
return qs.offset(offset).limit(limit).order_by(order)
```

### Issue: Template assumes `current_user` is not None

**File**: `app/ui/templates/index.html.j2` (line 54)

The expression `upload.user.id == current_user.id` will raise `AttributeError` if `current_user` is `None` (anonymous visitor viewing public uploads that were uploaded by another user).  This currently doesn't crash because `current_user` is set by middleware, but it deserves a guard.

**Fix**: Add a null check, e.g. `{% if current_user and upload.user.id == current_user.id %}`

### Issue: Image cards are not clickable

**File**: `app/ui/templates/index.html.j2` (line 9)

The `<img>` tag for image uploads is not wrapped in an `<a>` link, so users cannot click through to view the upload detail page.  Non-image file icons *are* linked (line 11).

**Fix**: Wrap the image `<img>` in an `<a href="{{ upload.view_url }}">` tag.

### Missing: View count not displayed on cards

**File**: `app/ui/templates/index.html.j2`

The implementation plan specifies displaying view count (`upload.viewed`) on each card, but this is not currently rendered in the template.

### Task: Remove test workarounds after bug fixes

Once the `UserSerializer.last_seen_at` bug is fixed:
1. Remove the `_create_user()` helper from `tests/test_ui_home_gallery.py`
2. Replace all `_create_user()` calls with direct `User.create()` calls (without providing `last_seen_at`)
3. Verify all 35 gallery tests still pass
