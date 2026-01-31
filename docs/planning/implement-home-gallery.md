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
- Home page exists at `/` but is nearly empty
- Template extends base layout but has no content
- Upload model has pagination support via `PaginationMixin`
- Upload model has `url` property for linking
- No gallery component exists
- No filtering for public uploads
- Profile page has similar gallery for user's uploads

### Target State
- Home page displays grid of latest public uploads
- Only public uploads (private=0) shown
- Pagination working with page controls
- Responsive grid layout (1-4 columns based on screen size)
- Each upload shows thumbnail, title, view count
- Click on upload navigates to view page
- Clean, modern design matching site theme
- Fast page load with optimized queries
- All tests passing

---

## Step 1: Update Home Route with Upload Query

**Files**: 
- `app/ui/main.py`
- `app/models/uploads.py` (if needed)

**Tasks**:
1. [ ] Update home route to fetch public uploads
2. [ ] Filter for public uploads only (private=0)
3. [ ] Order by created_at descending (newest first)
4. [ ] Add pagination support
5. [ ] Prefetch related data (images, user)
6. [ ] Pass uploads and pagination data to template
7. [ ] Handle empty state (no uploads)

**Tests**:
1. [ ] Test home route returns public uploads only
2. [ ] Test private uploads excluded
3. [ ] Test uploads ordered by newest first
4. [ ] Test pagination works
5. [ ] Test related data prefetched
6. [ ] Test empty state handled

**Acceptance Criteria**:
- [ ] Home route fetches correct uploads
- [ ] Only public uploads returned
- [ ] Pagination functional
- [ ] Efficient database queries
- [ ] All tests passing

**Implementation Notes**:
- Query: `Upload.filter(private=0).order_by('-created_at').prefetch_related('images', 'user')`
- Use `PaginationParams` dependency for pagination
- Page size: 24 uploads (works well with 4x6, 3x8, 2x12 grid layouts)
- Add database index via migration: `CREATE INDEX idx_uploads_private_created ON uploads(private, created_at DESC)`
- Handle case where no public uploads exist yet

---

## Step 2: Create Gallery Grid Component

**Files**: 
- `app/ui/templates/index.html.j2`
- `app/ui/templates/components/upload-grid.html.j2` (new)
- `app/ui/templates/components/upload-card.html.j2` (new)

**Tasks**:
1. [ ] Create reusable upload grid component
2. [ ] Create upload card component for individual items
3. [ ] Implement responsive grid layout (CSS Grid or Tailwind)
4. [ ] Display upload thumbnail/preview
5. [ ] Display upload title (or filename if no title)
6. [ ] Display view count
7. [ ] Display uploader username
8. [ ] Link card to upload view page
9. [ ] Add hover effects

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
1. [ ] Create pagination component (or reuse existing)
2. [ ] Display page numbers
3. [ ] Add previous/next buttons
4. [ ] Show current page indicator
5. [ ] Calculate total pages
6. [ ] Generate page links with query parameters
7. [ ] Handle edge cases (first page, last page)
8. [ ] Make mobile-friendly

**Tests**:
1. [ ] Test pagination displays correctly
2. [ ] Test page links work
3. [ ] Test previous/next buttons
4. [ ] Test first page (no previous)
5. [ ] Test last page (no next)
6. [ ] Test middle pages
7. [ ] Test mobile display

**Acceptance Criteria**:
- [ ] Pagination functional
- [ ] All page navigation works
- [ ] Edge cases handled
- [ ] Mobile responsive
- [ ] All tests passing

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
1. [ ] Create empty state component
2. [ ] Display message when no uploads exist
3. [ ] Add CTA button linking to upload page
4. [ ] Add loading skeleton for initial page load
5. [ ] Add loading states for pagination
6. [ ] Style empty state attractively

**Tests**:
1. [ ] Test empty state displays when no uploads
2. [ ] Test empty state hidden when uploads exist
3. [ ] Test loading skeleton displays
4. [ ] Test CTA button links to /upload
5. [ ] Test loading states for pagination

**Acceptance Criteria**:
- [ ] Empty state displays correctly
- [ ] Loading states improve UX
- [ ] CTA functional
- [ ] All tests passing

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
