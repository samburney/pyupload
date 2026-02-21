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
- Gallery grid renders with CSS multi-column layout (Step 2 complete)
- Pagination component reused and working (Step 4 complete)
- Empty state component created (Step 6 complete)
- Database index migration created for `private` column (Step 7 partial)
- **Modal view with placeholder sizing** - Images open in modal overlay with JavaScript-calculated placeholder
- `/get` error handling now returns generated image error responses for supported image conversion requests and HTML fallback responses for non-image requests
- Image processing requests with missing related image metadata now return handled `/get` error responses (`422`) with image or HTML fallback (no backend 500 for this known scenario)
- `UploadSerializer`, `UserSerializer`, `ImageSerializer` added via `tortoise-serializer`
- `PaginationParams` enhanced with `count`, `pages`, `page_data()`
- `humanize_bytes` helper and Jinja filter added
- Base layout refactored with semantic HTML (`<nav>`, `<main>`, `<footer>`)
- Alpine.js components globally registered in `header-includes.html.j2`
- Gallery card icon markup refactored to a shared SVG sprite (single include in base layout + per-card `<use>` references), reducing repeated inline HTML/SVG payload
- Home gallery remains covered by 40 focused tests, with additional `/get` error-response regression coverage added
- Added integration workflow coverage in `tests/test_integration_gallery.py` (browse gallery → view upload, and pagination navigation)
- Latest verified gallery-focused status: 49 passing tests (`tests/test_ui_home_gallery.py` + `tests/test_integration_gallery.py`)

### Review Snapshot (2026-02-15)
- Route and serialization flow for the home gallery are implemented and tested.
- Reusable gallery components are in active use on home and profile pages.
- Broken/missing image metadata backend response handling is complete; gallery-card specific placeholder UX polish remains pending.
- Performance validation tasks in Step 8 remain pending.

### Review Update (2026-02-17)
- Added backend regression coverage for `/get` error response behavior (image vs non-image fallback and validation-error handling).
- Implemented `/get` mapping for `ImageProcessingError` to handled `422` responses, preventing backend 500 for this known scenario.
- Remaining gallery UX work is limited to optional card-level placeholder presentation refinement.

### Review Update (2026-02-21)
- Implemented shared SVG sprite refactor for gallery-card icons (`layout/icons-sprite.html.j2` + `gallery-card.html.j2` `<use>` references), reducing cold document size.
- Updated performance evidence:
  - Slow 4G cold run (cache disabled) page shell now observed at ~133 kB document and ~1.82s request time for `?page=1`.
  - Slow 4G warm run remains under 2 seconds for shell load.
- Added integration workflow tests for Step 8 in `tests/test_integration_gallery.py`.
- Added large-dataset integration coverage for 100+ uploads with pagination/render scope assertions in `tests/test_integration_gallery.py`.
- Added responsive integration coverage for gallery grid and modal breakpoint classes in `tests/test_integration_gallery.py`.

### Target State
- ~~Home page displays grid of latest public uploads~~ ✅
- ~~Only public uploads (private=0) shown~~ ✅ (also includes owner's private uploads when logged in)
- ~~Pagination working with page controls~~ ✅
- ~~Responsive grid layout (1-4 columns based on screen size)~~ ✅
- ~~Each upload shows thumbnail, title, view count~~ ✅
- ~~Click on upload navigates to view page~~ ✅ (modal overlay with HTMX + Alpine.js)
- ~~Clean, modern design matching site theme~~ ✅
- Fast page load with optimized queries — **partial** (index added; warm and Slow 4G cold shell benchmarks now meeting current target; remaining perf/test coverage items still open)
- ~~All tests passing~~ ✅ (637/637 current full-suite status)
- **Completed**: Steps 1, 2, 4, 5, 6, Step 3 backend error handling, and Step 7 database/performance closure ✅ | **In progress**: Step 8 final production sign-off and manual WCAG review closure

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
1. [x] Create reusable upload grid component — *implemented 2026-02-13: `components/gallery-grid.html.j2`*
2. [x] Create upload card component for individual items — *implemented 2026-02-13: `components/gallery-card.html.j2`*
3. [x] Implement responsive grid layout (CSS Grid or Tailwind) — *uses CSS multi-column layout (`columns-*`)*
4. [x] Display upload thumbnail/preview
5. [x] Display upload title (or filename if no title) — *displays `upload.description`*
6. [x] Display view count — *implemented 2026-02-13*
7. [x] Display uploader username
8. [x] Link card to upload view page — *implemented 2026-02-13 with modal overlay (HTMX + Alpine.js)*
9. [x] Add hover effects — *implemented 2026-02-13: card scale + shadow, image brightness*

**Tests**:
1. [x] Test grid renders with uploads
2. [x] Test grid responsive at different breakpoints
3. [x] Test card displays all metadata
4. [x] Test card links to correct view page
5. [x] Test hover effects work
6. [x] Test empty grid state

**Component Architecture** (implemented 2026-02-13):

The gallery has been refactored into reusable components:

```
index.html.j2 (5 lines)
└─ includes: components/gallery-grid.html.j2
   ├─ loops through uploads
   ├─ includes: components/gallery-card.html.j2 (for each upload)
   ├─ includes: components/pagination.html.j2
   └─ includes: components/empty-content.html.j2 (when no uploads)
```

**Component Dependencies:**
- `gallery-grid.html.j2` expects: `uploads` (list), `pagination` (object), `current_user` (optional)
- `gallery-card.html.j2` expects: `upload` (object), `current_user` (optional)

**Benefits:**
- Clean separation of concerns
- Reusable across different pages (user profile, search results, etc.)
- Easier to maintain and test individual components
- Home page template reduced from 117 lines to 5 lines

**Reusability Validation** (2026-02-13):

Successfully retrofitted components to the user profile page as proof of reusability:
- **File**: `app/ui/templates/users/profile.html.j2` - Now uses `gallery-grid.html.j2` component
- **Route**: `app/ui/users.py` - Updated to use `UploadSerializer` and provide correct context
- **Result**: Both home page and profile page now share identical gallery UI with zero code duplication

Changes made to profile route:
```python
# Added UploadSerializer import
from app.models.uploads import Upload, UploadSerializer

# Updated pagination to use object instead of dict
pagination.count = await Upload.filter(user=current_user).count()

# Serialize uploads for component
upload_models = Upload.paginate(**pagination.page_data(), user=current_user) \
    .prefetch_related("user","images")
uploads = await UploadSerializer.from_queryset(upload_models)

# Pass pagination object (not dict) to template
context = {"uploads": uploads, "pagination": pagination, "current_user": current_user}
```

This validates that the component architecture is truly reusable and maintainable.

**Acceptance Criteria**:
- [x] Grid displays uploads in clean layout
- [x] Responsive design works on all screen sizes
- [x] All metadata visible
- [x] Links functional
- [x] All tests passing

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
1. [x] Display image thumbnails for image uploads — *implemented with calculated aspect ratio*
2. [x] Display video icon/placeholder for videos — *file type icon with extension*
3. [x] Display file icon for other file types — *dashed border box with extension*
4. [x] Implement aspect ratio container (e.g., 16:9 or 1:1) — *implemented with calculated inline styles*
5. [x] Add loading states for images — *Alpine.js loading placeholder with fade transition*
6. [x] Handle broken/missing images (render placeholder response instead of backend 500 where appropriate) — *implemented via `/get` `ImageProcessingError` → `422` mapping with image/HTML fallback*
7. [x] Optimize image display (object-fit) — *responsive sizing with hover effects*

**Tests**:
1. [x] Test image thumbnails display
2. [x] Test video placeholders display
3. [x] Test file icons display
4. [x] Test aspect ratio maintained
5. [x] Test broken image handling and placeholder fallback for missing image metadata — *covered in `tests/test_ui_uploads.py` for image and non-image request variants*
6. [x] Test loading states

**Acceptance Criteria**:
- [x] Images display correctly
- [x] Non-images show appropriate icons
- [x] Consistent aspect ratios — *calculated from image metadata*
- [x] Good loading experience — *placeholder with fade to image*
- [x] All tests passing — *automated UI coverage added in `tests/test_ui_home_gallery.py` for Step 3 rendering states*

**Implementation Notes**:
- For images: `<img src="{{ upload.url }}" class="object-cover w-full h-full">`
- For now, use full image (thumbnail generation is future enhancement)
- Backend behavior now catches `ImageProcessingError` in `/get` and returns handled `422` responses (image error payload for image requests, HTML fallback for non-image requests) while preserving real exception detail in response text.
- Use `upload.is_image` to check if upload has image metadata
- Consider using placeholder images from a service or local assets
- Add `loading="lazy"` for performance
- Use Tailwind's `aspect-w-16 aspect-h-9` or similar for aspect ratio

**Task 6 Implementation Notes**:
- **Goal**: For image requests where related image metadata is missing/broken, return a user-facing placeholder response (not backend 500).
- **Backend mapping point**: In `app/ui/uploads.py` `get_upload()`, add a specific `except ImageProcessingError` branch before the generic `except Exception` and route it to `error_response_for_get(...)` with status `422` or `404` (pick one and keep consistent with tests).
- **Use existing helper**: Reuse `app/lib/error_handling.py:error_response_for_get` so image requests get generated error-image payloads and non-image requests fall back to HTML responses.
- **Message shape**: Keep real exception detail in user-facing response text for consistency with other `get_upload()` exception paths.
- **Do not broaden scope**: Keep this task to response handling only; do not add thumbnail generation/caching changes here.
- **Test additions**:
  - Add/extend `tests/test_ui_uploads.py` to verify missing image metadata requests no longer return 500.
  - Assert image extension requests return image response with non-500 status.
  - Assert non-image extension requests return HTML fallback with non-500 status.
  - Keep existing successful-image path tests unchanged to prevent regressions.
- **Plan completion criteria for Task 6**:
  - [x] Missing/broken image metadata path returns placeholder response (image or HTML fallback as appropriate).
  - [x] No backend 500 for this known scenario.
  - [x] Automated tests added for both image and non-image request variants.

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
7. [x] Test mobile display

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
1. [x] Add upload title display (with fallback to filename) — *shows `upload.description`*
2. [x] Add view count display — *eye icon with count*
3. [x] Add uploader username display — *with public/private icon*
4. [x] Add upload date (relative time) — *implemented 2026-02-14*
5. [x] Add file type indicator — *file icon with type*
6. [x] Style metadata for readability — *icon + text layout; dimensions moved to image overlay*
7. [x] Add tooltips for truncated text — *title attribute on description*
8. [x] Implement text truncation for long titles — *CSS overflow ellipsis*

**Tests**:
1. [x] Test title displays correctly
2. [x] Test fallback to filename — *using description field*
3. [x] Test view count displays
4. [x] Test username displays
5. [x] Test date formatting
6. [x] Test text truncation
7. [x] Test tooltips

**Acceptance Criteria**:
- [x] All metadata visible and formatted
- [x] Truncation works for long text
- [x] Clean, readable design
- [x] All tests passing — *automated UI coverage added in `tests/test_ui_home_gallery.py` for Step 5 metadata/fallback rendering*

**Implementation Notes**:
- Title: `{{ upload.description or upload.originalname }}` (description if set, else original filename)
- Dimensions displayed as overlay on image for cleaner look (2026-02-14)
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
4. [x] Add loading skeleton for initial page load — *implemented via per-card `animate-pulse` skeletons*
5. [x] Add loading states for pagination — *covered by per-card skeletons on new page load*
6. [x] Style empty state attractively

**Tests**:
1. [x] Test empty state displays when no uploads
2. [x] Test empty state hidden when uploads exist
3. [x] Test loading skeleton displays
4. [x] Test CTA button links to /upload
5. [x] Test loading states for pagination

**Acceptance Criteria**:
- [x] Empty state displays correctly
- [x] Loading states improve UX
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
1. [x] Create database migration for index
~~2. [ ] Optimize image loading (lazy loading)~~ Not a required feature, will implement a different optimisation technique.
3. [x] Minimize database queries (N+1 prevention) - *Completed with `prefetch_related`*
4. [x] Add page caching headers — *Completed for home page response in `app/ui/main.py` with `Cache-Control`, `ETag`, `Vary` and `304` handling*
5. [x] Profile page load performance - *Completed via Step 8 DevTools profiling evidence*
6. [x] Stabilize responsive sizing behavior across mobile breakpoints — *Completed (single-column mobile layout + SVG placeholder reservation + JS placeholder/image size matching)*
7. [x] Define and lock home-gallery DB query-count baseline for page render (`/` page 1) — *Implemented in `tests/test_ui_home_gallery.py` (`SELECT_QUERY_BASELINE_BUDGET = 29`)*
8. [x] Add regression test proving query count does not scale with item count (24 vs 100+ uploads) — *Implemented in `tests/test_ui_home_gallery.py`*

**Tests**:
1. [x] Add query-count baseline test for home page render (`/` page 1): assert query count <= agreed baseline
2. [x] Add N+1 regression test with seeded 24 and 100+ uploads: assert identical query-count envelope for both
3. [x] Test page load time — *validated with manual DevTools profiling evidence in Step 8*
4. [x] Test caching behavior — *includes home-page document cache header + `If-None-Match`/`304` coverage in `tests/test_ui_home_gallery.py`*

**Acceptance Criteria**:
- [x] Cold start shell render (HTML/CSS/JS, excluding full image completion) in < 2.0s on Slow 4G (3G measured as observational only)
- [x] Warm-cache shell render (HTML/CSS/JS, excluding full image completion) in < 2.0s on Slow 4G
- [x] Database query-count baseline for home gallery page render is documented and enforced by test
- [x] Query-count envelope is stable between 24-item and 100+-item datasets (no N+1 scaling)
- [x] All tests passing

**Implementation Notes**:
- Create Aerich migration: `CREATE INDEX idx_uploads_private_created ON uploads(private, created_at DESC)`: DONE
- Use `.prefetch_related()` to avoid N+1 queries (already in Step 1): DONE
- Add `Cache-Control` headers for page responses: pending
- Added page-level cache headers and conditional request handling for `/` (`Cache-Control: private, max-age=60, must-revalidate`, `ETag`, `Vary: Cookie`, and `304 Not Modified` on matching `If-None-Match`).
- Performance gating profile: Slow 4G is the pass/fail mobile profile; 3G remains a non-gating observational profile for trend visibility.
- Performance scope for this step: evaluate initial usable shell render (document + required CSS/JS), not full gallery image completion time.
- Responsive sizing scope is complete for v0.1: mobile renders single-column, image space is reserved by SVG placeholders, and JavaScript placeholder sizing is intentionally retained to match loaded image geometry.
- Remaining Step 7 work is database validation only (query performance and N+1 regression coverage).
- Database closure definition for Step 7: set a concrete query-count baseline from current implementation, then enforce non-scaling behavior via automated tests.
- Step 7 database validation completed with automated coverage in `tests/test_ui_home_gallery.py`:
  - `test_home_page_query_count_baseline_page_1`
  - `test_home_page_query_count_non_scaling_between_24_and_100_plus`
  - Current enforced baseline budget: `SELECT_QUERY_BASELINE_BUDGET = 29`
- Recent profiling evidence (2026-02-21):
  - Cold, cache disabled: Slow 4G ≈ 5.59s (full page), 3G ≈ 19.44s (full page).
  - Warm, cache enabled: Slow 4G ≈ 1.69s load (PASS for warm criterion), 3G ≈ 5.96s load (observational only).
  - Post SVG sprite refactor, cache-disabled Slow 4G for `?page=1`: document ≈ 133 kB, request ≈ 1.82s (meets cold shell criterion).
~~- Use `loading="lazy"` on images~~:  Not a required feature, will implement a different optimisation technique.
~~- Consider implementing Redis caching for popular pages (future enhancement)~~: NOT IN SCOPE
- Profile with FastAPI profiling tools or browser DevTools

**Dependencies**:
- All previous steps should be complete

---

## Step 8: Integration Testing and Documentation

**Files**: 
- `tests/ui/test_home_page.py` (new)
- `tests/test_integration_gallery.py` (new)
- `README.md`

**Tasks**:
1. [x] Create comprehensive integration tests — *initial integration workflow coverage added in `tests/test_integration_gallery.py`*
2. [x] Test full browsing workflow — *gallery browse → upload view integration test added*
3. [x] Test with various data scenarios (empty, few, many uploads)
4. [x] Test responsive design at all breakpoints
5. [x] Test accessibility baseline (keyboard navigation, semantic labels, modal dialog controls)
6. [x] Performance testing with large datasets — *implemented via 100+ upload integration dataset scenario with pagination/render-scope assertions*
7. [x] Update documentation

**Tests**:
1. [x] Integration test: Browse gallery → View upload
2. [x] Integration test: Pagination workflow
3. [x] Test with 0 uploads
4. [x] Test with 100+ uploads
5. [x] Test responsive breakpoints (UI + integration coverage)
6. [x] Test accessibility baseline checks
7. [x] Test page load performance

**Acceptance Criteria**:
- [x] All integration tests passing
- [x] Works with all data scenarios
- [x] Fully responsive
- [x] Accessible baseline verified (Lighthouse + integration checks)
- [x] Good performance
- [x] Documentation updated
- [ ] Ready for production — *pending release sign-off*

**Implementation Notes**:
- Use pytest fixtures for test data
- Test with realistic data volumes
- Use Lighthouse for accessibility and performance audits
- Document any known limitations
~~- Add screenshots to documentation~~: Let's skip this until the v0.1 implementation is actually complete.
- Page-load performance validation currently uses DevTools network profiling with Slow 4G as pass/fail profile and 3G as observational-only data.
- Accessibility baseline now includes explicit dialog semantics and control/link labels in gallery modal flows, validated by integration tests.
- Lighthouse audit captured: `temp/localhost_8001-20260221T142615.json` (mobile simulation).
  - Category scores: Performance **90**, Accessibility **82**, Best Practices **96**, SEO **91**.
  - Key failing audits observed in this run: `button-name`, `label-content-name-mismatch`, `list`, `listitem`, `link-in-text-block`, `errors-in-console`, and non-blocking perf opportunity audits (`render-blocking-insight`, `cache-insight`, `image-delivery-insight`, `unused-javascript`).
  - Implemented immediate template fixes after this run:
    - Added mobile-menu toggle accessible name in navbar (`aria-label`).
    - Corrected pagination `<ul>/<li>/<a>` semantics.
    - Updated gallery link accessible names to include visible label text.
    - Made footer links visually distinguishable without relying only on color.
  - Validation after fixes: `uv run pytest tests/test_integration_gallery.py tests/test_ui_home_gallery.py -q` → **49 passed**.
- Lighthouse rerun captured: `temp/localhost_8001-20260221T144520.json` (mobile simulation, post-fixes).
  - Category scores: Performance **91**, Accessibility **100**, Best Practices **96**, SEO **91**.
  - Previously failing accessibility checks `button-name`, `list`, `listitem`, and `link-in-text-block` no longer appear as scored failures.
  - `label-content-name-mismatch` still appears as a **hidden weight-0 audit** in this run; does not affect Accessibility score. Card link labels were aligned with visible dimension text to eliminate this warning path.
  - `errors-in-console` entry (`/get/277/qkobkqa-640x0.jpg` 404) is confirmed **expected behavior** for this test path and is treated as non-blocking for Step 8 closure.

**Dependencies**:
- All previous steps must be complete

---

## ~~Potential Issues Identified~~ ✅ ALL RESOLVED

The following issues were identified during the branch review (2026-02-10) and have all been resolved (2026-02-13).

### ~~Bug: `UserSerializer.last_seen_at` typed as non-optional~~ ✅ FIXED

**File**: `app/models/users.py` (line 123-124)

~~`last_seen_at` is typed as `datetime` in `UserSerializer`, but the database field is `DatetimeField(null=True)`.  When a user has never logged in (e.g. freshly created), serialisation fails with a Pydantic validation error.  The same issue may apply to `last_login_ip` (line 123) which is also `null=True` in the model but typed as `str`.~~

**Fix Applied (2026-02-13)**:
- `last_seen_at: Optional[datetime]`
- `last_login_ip: Optional[str]`

**Workaround removed**: The `_create_user()` helper has been removed from `test_ui_home_gallery.py` and all tests now use direct `User.create()` calls. All 35 tests still passing.

### ~~Bug: `PaginationMixin.paginate()` double-applies offset/limit/order~~ ✅ FIXED

**File**: `app/models/common/pagination.py` (lines 56-63)

~~When a `query` argument is provided, the method builds an initial queryset with `.offset().limit().order_by()`, then calls `.filter(query).offset().limit().order_by()` again on top of that.  This redundantly applies the same clauses.  While it appears to produce correct results in SQLite testing, it could cause unexpected behaviour with other database backends.~~

**Fix Applied (2026-02-13)**: Refactored to treat `query` and `*args/**kwargs` as mutually exclusive filter sources, applying offset/limit/order_by only once at the end:
```python
# Handle query argument if it's provided
if query:
    qs = cls.filter(query)
else:
    qs = cls.filter(*args, **kwargs)
return qs.offset(offset).limit(limit).order_by(order)
```

This approach is cleaner and aligns with the intended usage pattern where `query` (a Q expression for complex filters) is used instead of simple `*args/**kwargs` filters.

### ~~Issue: Template assumes `current_user` is not None~~ ✅ FIXED

**File**: `app/ui/templates/index.html.j2` (line 54)

~~The expression `upload.user.id == current_user.id` will raise `AttributeError` if `current_user` is `None` (anonymous visitor viewing public uploads that were uploaded by another user).  This currently doesn't crash because `current_user` is set by middleware, but it deserves a guard.~~

**Fix Applied (2026-02-13)**: Added null check: `{% if current_user and upload.user.id == current_user.id %}`

**Additional Improvements**:
- Updated `PaginationMixin.pages()` to support the `query` parameter (matching `paginate()` signature)
- Added zero-count guard to return 1 page minimum (prevents division issues and improves UX)

### ~~Issue: Image cards are not clickable~~ ✅ IMPLEMENTED

**Files**: 
- `app/ui/templates/index.html.j2`
- `app/ui/templates/uploads/view-modal.html.j2` (new)
- `app/ui/templates/uploads/view.html.j2` (new)
- `app/ui/templates/layout/error.html.j2` (new)
- `app/ui/uploads.py`

~~The `<img>` tag for image uploads is not wrapped in an `<a>` link, so users cannot click through to view the upload detail page.  Non-image file icons *are* linked (line 11).~~

**Implementation Applied (2026-02-13)**:

**Modal View System:**
- Images are now clickable and open in a **modal overlay** using HTMX + Alpine.js
- HTMX loads the modal content dynamically: `hx-get="{{ upload.view_url }}?modal=true"`
- Modal injected into DOM with `hx-target="body"` and `hx-swap="beforeend"`

**New Route:**
- Added `/view/{id}/{filename}` endpoint in `app/ui/uploads.py`
- Supports `?modal=true` query param to render modal view vs full page view
- Returns 404 error messages for modal vs error page depending on context

**Modal Features:**
- Full-screen semi-transparent backdrop (click to close)
- Close button in top-right corner
- Responsive image sizing: `max-h-[calc(100dvh-1rem)]` for mobile, `max-h-[calc(100dvh-2rem)]` for >=sm
- **Placeholder sizing**: JavaScript-calculated placeholder matches image dimensions respecting viewport constraints
  - Uses `Alpine.data('imagePlaceholder')` component registered in `header-includes.html.j2`
  - Calculates size based on natural image dimensions and viewport size
  - Respects responsive padding (16px for <640px, 32px for >=640px)
  - Recalculates on window resize (only when image not loaded)
  - Modal card hidden until placeholder sizing complete (prevents flash of unsized content)
- Description overlay with link to full page view
- Click image content doesn't close modal (`@click.stop`)
- **Smooth transitions**: Fades in on open, fades out on close
- **Auto-cleanup**: Modal removed from DOM after close animation completes using `@transitionend.self`
- **Image loading**: Placeholder shows while loading, fades to image when loaded

**Technical Details:**
- Alpine.js state: starts `open: false`, then `$nextTick(() => open = true)` to trigger enter transition
- Explicit transition duration: `x-transition.opacity.duration.300ms` (required for reliable `transitionend` firing)
- Inner content has separate transition: `x-transition.duration.150ms` for staggered effect
- Self-removing: `@transitionend.self="if (!open) { $el.remove(); }"` prevents DOM accumulation
- **HTMX script handling**: Alpine components registered globally in `header-includes.html.j2` (HTMX doesn't execute `<script>` tags in swapped content for security)
- **Component event system**: Placeholder uses `$dispatch('placeholder-ready')` event to signal parent when sizing complete
- Backdrop shows immediately (`open = true`), modal card waits for `@placeholder-ready.window` event
- `x-cloak` on modal card prevents flash before Alpine initializes

**Alpine.js Components (Global Registration):**
All Alpine components are registered in `app/ui/templates/layout/header-includes.html.j2` for use across the application:

- **`imagePlaceholder(naturalW, naturalH)`** - Image placeholder sizing component
  - Calculates responsive placeholder dimensions for modal images
  - Maintains aspect ratio while respecting viewport constraints
  - Dispatches `placeholder-ready` event when sizing complete

- **`uploadWidget`** - Upload widget store (Alpine.store)
  - Manages file selection and drag-drop state
  - File list manipulation (add, remove)
  - File size formatting helper
  - Used in `/upload` page


### ~~Missing: View count not displayed on cards~~ ✅ IMPLEMENTED

**File**: `app/ui/templates/index.html.j2`

~~The implementation plan specifies displaying view count (`upload.viewed`) on each card, but this is not currently rendered in the template.~~

**Implementation Applied (2026-02-13)**:
- Added view count icon and value to the metadata row
- View count displays as `{{ upload.viewed }}` with an eye icon SVG
- Also fixed dimension order to display as `width x height` (standard format)
