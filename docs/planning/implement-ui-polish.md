# Implementation Plan: UI Polish and Navigation

## Overview

Polish the user interface with improved navigation, responsive design refinements, and user experience enhancements to complete the v0.1 release.

### Scope
- Complete responsive navigation menu with backdrop and conditional user links
- Implement three-tier authentication UI (anonymous, unregistered auto-accounts, registered users)
- Refine mobile breakpoint styling
- Polish existing flash message system (add icons, auto-dismiss, close button)
- Add breadcrumb navigation (context processor-based)
- Add gallery discovery pages (/random, /popular, /all)
- Add static content pages (About, Privacy, Terms, Contact)
- Update footer with git-based version information
- Improve form styling and validation feedback (critical for v0.1)
- Accessibility improvements and testing

### Current State
- Navbar exists with Alpine.js dropdowns and mobile toggle
- Mobile menu lacks backdrop, conditional user links, and outside-click-to-close
- User dropdown shows same links for all users (needs three-tier auth logic)
- Flash messages fully implemented with Alpine.js (needs icons and auto-dismiss)
- Footer exists with copyright (needs version info and additional links)
- No breadcrumbs
- Forms are functional with HTMX and baseline Tailwind styling, but need consistency and validation polish
- Navbar links include unimplemented routes that need cleanup (/uploads, /search, /random, /popular, /all) — `/tags` and `/collections` are now implemented

### Review Snapshot (2026-04-26)
- `/search` route implemented in `app/ui/search.py` — keyword search across upload description, name, originalname, and tag names; collection name search when authenticated
- Full-page and HTMX partial rendering (`search/index.html.j2`, `search/results.html.j2`, `search/partials/results_output.html.j2`, `search/partials/query_form.html.j2`)
- `build_text_search_filter(query, user)` and `build_qs_filter(query_string, user)` added to `app/ui/common/gallery.py`; `build_qs_filter` now returns `None` (not `Q()`) when no recognised params are present — callers use `is not None` guards
- `PaginationParams.page_url()` method added to `app/models/common/pagination.py` — builds query strings preserving `extra_params` and omitting pagination params that match subclass defaults; used by all pagination templates so search query is preserved across page navigation
- `enable_super_select` template variable introduced — search results, tags, and collections pages pass `True`; gallery index passes `True` only when a `context_filter` is active; multiselect control renders the "Select all" option only when enabled
- `build_writable_upload_queryset` guard added: `super_selected=True` with `context_filter=None` returns an empty queryset, preventing accidental bulk action against all writable uploads with no scope
- `readable_upload_queryset` updated: applies `.distinct()` when a `context_filter` is present; changed to `is not None` check so an explicit `Q()` is treated as a valid "select everything" scope
- Desktop navbar `/uploads` and `/search` links now point to implemented routes
- Tests added: `tests/test_models_common_pagination.py` (11 tests), new classes in `tests/test_ui_common_gallery.py` (`TestBuildTextSearchFilter`, `TestBuildQsFilter`), `tests/test_ui_search.py` (18 tests); all 1193 tests passing

### Review Snapshot (2026-02-15)
- Core Tailwind + Alpine UI scaffolding is in place and functional.
- Responsive/navbar polish tasks are still largely open.
- Discovery routes (`/random`, `/popular`, `/all`) and static routes (`/about`, `/privacy`, `/terms`, `/contact`) are still not implemented.
- Navbar still includes links to unimplemented pages (`/uploads`, `/search`) that should be fixed or removed until routes exist — `/tags` and `/collections` are now implemented.
- Breadcrumbs, footer versioning, and accessibility pass are still pending.

### Review Snapshot (2026-03-07)
- CSS architecture overhauled on `implement-upload-view-page` branch: all component styles (`button`, `split-button`, `menu`, `message`, `pagination`, `tag-item`) migrated from `@layer components` to individual `@utility` rules with CSS nesting. This establishes the styling foundation that the UI polish plan builds on.
- Default Tailwind breakpoints restored (Bootstrap 4 overrides removed). Custom `3xl`, `4xl`, `5xl` breakpoints added for large displays.
- Responsive `md:max-lg:` modifiers added to sidebar components (split buttons, tags, share button, toggle, download chevron) — partial progress on Step 3.
- Breakpoint debug indicator added to `base.html.j2` footer (gated behind `config.debug`) — useful for Step 3 testing.
- Tag items now use a hover-to-reveal delete button pattern (`tag-item`, `tag-remove` utilities).
- Global anchor `<a>` base styles intentionally removed for normalisation; needs re-establishing before merge — relates to Step 9 (form styling) and general UI consistency.
- All other steps remain open.

### Review Snapshot (2026-04-12)
- Breadcrumb system fully implemented via `app/ui/common/breadcrumbs.py`
- `Breadcrumbs` class uses a module-level factory (router + title config); `handle_request` produces a fresh per-request instance — no concurrency hazard
- URL coercion handled via `TypeAdapter(HttpUrl).validate_python` at module level
- Breadcrumbs wired to `/gallery/`, `/gallery/index`, `/gallery/random`, and `/` (root delegates to gallery)
- Template uses filled SVG polygon cap after home icon, stroked SVG chevron for inner separators; current page shown bold and not linked
- Tests added in `tests/test_ui_common_breadcrumbs.py`

### Review Snapshot (2026-04-22)
- `/popular` and `/all` routes added to both `app/ui/gallery.py` and `app/ui/main.py` (root-level aliases)
- Routes share `gallery_index_get` handler; path detected via `request.url.path.endswith(...)` to override sort params
- `/popular`: sorts by `viewed` desc, standard pagination
- `/all`: sorts alphabetically by description asc, infinite scroll enabled — **deviates from original plan** ("same as home") but is intentionally differentiated
- `selection_handler` removed from gallery context — template uses Jinja2 `url_for()` directly; confirmed no template references remain
- Tests added for both routes: visibility, sort order, pagination, infinite scroll, root-level aliases
- All 1141 tests passing

### Review Snapshot (2026-04-21)
- `/random` gallery implemented as a seeded-shuffle paginated grid with infinite scroll — deviates from original plan (which described a redirect to a single upload view)
- `RandomGalleryPaginationParams` added to `app/ui/common/gallery.py` — isolates `seed`/`ps` alias and generation logic from the base model
- `infinite_scroll: bool = False` added to `PaginationParams` — available to all paginated views; pagination component switches modes based on this flag
- `random.html.j2` deleted — random gallery reuses `gallery/index.html.j2`
- Upload pool capped at 100,000 IDs per request; items within each page ordered by `created_at` desc
- Tests added for `RandomGalleryPaginationParams` (seed generation, `ps` alias, zero-seed edge case) and `gallery_random_get` (empty gallery, visibility, infinite scroll trigger, seed persistence, page non-overlap)

### Review Snapshot (2026-04-18)
- Collections gallery index (`GET /collections`) and individual collection upload view (`GET /collections/view/{name_unique}`) implemented in `app/ui/collections.py`
- `CollectionSelectionDetail` serializer extracted to `app/ui/common/collections.py` — mirrors `TagSelectionDetail` pattern with `SelectionDetail`, lazy-fetched `UploadSerializer` lists, and `readable_upload_queryset`/`writable_upload_queryset` base functions
- `TagSelectionDetail` and `TagPaginationDefaultParams` similarly extracted from `app/ui/common/gallery.py` into `app/ui/common/tags.py`
- `readable_upload_queryset` and `writable_upload_queryset` base functions added to `app/ui/common/uploads.py`; `context_filter: Q` parameter threads through `build_readable_upload_queryset`, `build_writable_upload_queryset`, and `get_writable_selected_uploads`
- Per-route `selection_handler` URL now passed as template context variable, decoupling the shared gallery template from route names
- `POST /collections/view/{name_unique}/update-selected` and `POST /tags/view/{name}/update-selected` multiselect sidebar handlers added
- `info_template_response` helper added to `app/ui/common/errors.py` — renders green `message-ok` banner via `info_messages` context key (contrasted with `error_messages` → red `message-alert`)
- `Collection.view_url` property added; `Collection` now mixes in `PaginationMixin`; `CollectionSerializer` exposes `view_url`
- `/collections` navbar link is now a valid route — remove from "unimplemented routes" lists in Steps 1 and 2
- All 1106 tests pass; new test classes cover `GET /collections`, `GET /collections/view/{name}`, and `POST /collections/view/{name_unique}/update-selected`

### Review Snapshot (2026-04-17)
- Tags gallery index (`GET /tags`) and individual tag upload view (`GET /tags/view/{name}`) implemented in `app/ui/tags.py`
- `TagSelectionDetail` serializer added to `app/ui/common/gallery.py` — extends `TagSerializer` with `SelectionDetail`, lazy-fetched `UploadSerializer` lists, and readable/writable upload model resolution
- `get_selection_detail()` extracted from `render_multiselect_sidebar` as a standalone reusable async function; sidebar now delegates to it
- `default_readable_upload_tag_filter()` added to `app/ui/common/uploads.py` via a shared `_build_default_readable_filter` helper that accepts a `relation_prefix`
- `GalleryPaginationDefaultParams` moved from `app/ui/gallery.py` to `app/ui/common/gallery.py` for broader reuse
- `Tag.view_url` property added; `Tag` now mixes in `PaginationMixin`; `TagSerializer` exposes `view_url`
- New templates: `components/common/stack-card.html.j2`, `components/common/stack-grid.html.j2`, `tags/index.html.j2`
- New SVG sprite icons: `cards-stack`, `event`, `storage`, `unknown-document`
- ETag system extended to handle `SelectionDetail` objects alongside `UploadSerializer`
- `/tags` navbar link is now a valid route — remove from "unimplemented routes" lists in Steps 1 and 2
- All 1072 tests pass; new test class `TestTagsIndexEndpoint` covers visibility rules, pagination, ETag/304 behavior
- Planning doc for next tags feature (upload pile preview) added at `docs/planning/implement-upload-pile-preview.md`

### Review Snapshot (2026-03-09)
- Implemented `/random` gallery discovery page with random uploads display
- Added breadcrumbs template and layout integration (`layout/breadcrumbs.html.j2`, updated `base.html.j2`)
- Added home icon to SVG sprite for breadcrumbs
- Core random endpoint redirect from `/random` to `/gallery/random` working
- Breadcrumb template functional; automation of breadcrumb logic deferred to future enhancement
- Next feature: `/popular` page (most viewed) — plan to extract shared gallery view logic at this point

### Target State
- Fully responsive navbar with backdrop and conditional user content
- Three-tier authentication UI properly implemented
- Mobile menu with backdrop, animations, and outside-click-to-close
- Flash messages with icons, auto-dismiss, and minimal close button
- Breadcrumbs on deep pages (context processor-based)
- Gallery pages (/random, /popular, /all) implemented
- Static content pages (About, Privacy, Terms, Contact) created
- Footer with git-based version info and additional links
- Forms beautifully styled with validation feedback
- WCAG 2.1 AA accessibility compliance
- All tests passing

---

## Step 1: Improve Mobile Navigation Menu

**Files**: 
- `app/ui/templates/layout/navbar.html.j2`

**Tasks**:
1. [ ] Add semi-transparent backdrop/overlay when mobile menu is open
2. [ ] Add conditional user-specific links (same logic as Step 2)
3. [ ] Implement outside-click-to-close (click backdrop closes menu)
4. [ ] Ensure menu closes on link click
5. [ ] Improve open/close animations
6. [ ] Remove/fix links to unimplemented pages (/uploads, /search) — `/tags` and `/collections` are now implemented
7. [ ] Ensure keyboard navigation works (Escape to close)
8. [ ] Add ARIA labels for accessibility

**Tests**:
1. [ ] Test mobile menu opens/closes
2. [ ] Test backdrop displays when menu open
3. [ ] Test clicking backdrop closes menu
4. [ ] Test menu closes on link click
5. [ ] Test conditional links show correctly
6. [ ] Test Escape key closes menu
7. [ ] Test screen reader compatibility
8. [ ] Test on iOS and Android

**Acceptance Criteria**:
- [ ] Mobile menu fully functional with backdrop
- [ ] Conditional user links working
- [ ] Smooth animations
- [ ] Keyboard accessible
- [ ] Works on all devices
- [ ] All tests passing

**Implementation Notes**:
- Backdrop: `<div x-show="mobileMenuOpen" @click="mobileMenuOpen = false" class="fixed inset-0 bg-black bg-opacity-50 z-40"></div>`
- Menu z-index: 50 (above backdrop's 40)
- Close on Escape: `@keydown.escape.window="mobileMenuOpen = false"`
- Remove or remap unimplemented route links (`/uploads`, `/search`) until routes are implemented — `/tags` and `/collections` are now valid routes
- Mobile menu should show same conditional logic as desktop (see Step 2)
- Ensure smooth slide-in transition from top or side

---

## Step 2: Implement Three-Tier Authentication UI

**Files**: 
- `app/ui/templates/layout/navbar.html.j2`
- `app/ui/common/security.py` (if needed for template helpers)

**Tasks**:
1. [ ] Implement conditional rendering for three user tiers
2. [ ] **Truly anonymous users** (no current_user): Show Login + Register buttons (no dropdown)
3. [ ] **Unregistered auto-accounts** (current_user exists, not is_registered): Show Login + Register in dropdown, hide Logout
4. [ ] **Registered users** (current_user.is_registered): Show Profile, My Uploads, My Collections, Logout in dropdown
5. [ ] Remove Login/Register from dropdown for registered users
6. [ ] Update desktop user dropdown logic
7. [ ] Remove or remap unimplemented links from navbar (`/uploads`, `/search`) — `/tags` and `/collections` are now implemented
8. [ ] Style dropdown menu consistently

**Tests**:
1. [ ] Test truly anonymous user sees Login + Register buttons (no dropdown)
2. [ ] Test unregistered auto-account sees dropdown with Login + Register
3. [ ] Test unregistered auto-account does NOT see Logout
4. [ ] Test registered user sees dropdown with Profile, My Uploads, Logout
5. [ ] Test registered user does NOT see Login/Register in dropdown
6. [ ] Test dropdown opens/closes correctly
7. [ ] Test mobile behavior matches desktop logic
8. [ ] Test unimplemented route links are removed or replaced with valid routes

**Acceptance Criteria**:
- [ ] Three-tier authentication UI working correctly
- [ ] Truly anonymous users see Login + Register buttons
- [ ] Unregistered users behave like anonymous (UX perspective)
- [ ] Registered users see full account options
- [ ] All links functional
- [ ] Dropdown styled consistently
- [ ] All tests passing

**Implementation Notes**:
- **Truly Anonymous**: `{% if not current_user %}` → Show Login + Register buttons (no dropdown)
- **Unregistered Auto-Account**: `{% if current_user and not current_user.is_registered %}` → Dropdown with Login, Register, Profile (NO Logout)
- **Registered User**: `{% if current_user and current_user.is_registered %}` → Dropdown with Profile, My Uploads, My Collections, Logout
- UX Goal: Unregistered users should feel anonymous while having frictionless upload capability
- Remove "Not Logged In ▾" text (confusing for auto-accounts)
- Dropdown position: `absolute right-0 top-full`
- Use Alpine.js `x-data` for toggle state
- Remove or remap unimplemented links from desktop and mobile menus (`/uploads`, `/search`) — `/tags` and `/collections` are now valid routes

---

## Step 3: Refine Mobile Breakpoint Styling

**Files**: 
- `app/ui/templates/layout/base.html.j2`
- `app/ui/templates/layout/navbar.html.j2`
- All page templates

**Tasks**:
1. [ ] Review all pages at mobile breakpoints
2. [ ] Fix any layout issues on small screens
3. [ ] Ensure touch targets are large enough (44x44px minimum)
4. [ ] Test horizontal scrolling issues
5. [ ] Optimize font sizes for mobile
6. [ ] Test on real devices (not just browser DevTools)
7. [ ] Fix any z-index or overflow issues

**Tests**:
1. [ ] Test all pages at 320px width
2. [ ] Test all pages at 375px width
3. [ ] Test all pages at 768px width
4. [ ] Test touch target sizes
5. [ ] Test no horizontal scroll
6. [ ] Test on real iOS device
7. [ ] Test on real Android device

**Acceptance Criteria**:
- [ ] All pages work on mobile
- [ ] No horizontal scrolling
- [ ] Touch targets adequate
- [ ] Readable font sizes
- [ ] All tests passing

**Implementation Notes**:
- Use Tailwind responsive prefixes: `sm:`, `md:`, `lg:`
- Test breakpoints: 320px, 375px, 768px, 1024px, 1280px
- Minimum touch target: 44x44px (Apple HIG)
- Check for `overflow-x: hidden` on body if needed
- Test in both portrait and landscape orientations

**Dependencies**:
- Step 1 must be complete

---

## Step 4: Polish Flash Message System

**Files**: 
- `app/ui/templates/components/core/messages.html.j2`

**Tasks**:
1. [ ] Add icons for message types (info, success/ok, warning, error/alert)
2. [ ] Replace "Ok" button with minimal close "×" button
3. [ ] Add auto-dismiss timeout for info, ok, and warning messages (5 seconds)
4. [ ] Keep manual dismiss for error/alert messages
5. [ ] Improve icon styling and positioning
6. [ ] Ensure transitions remain smooth

**Tests**:
1. [ ] Test info message displays with info icon
2. [ ] Test success/ok message displays with checkmark icon
3. [ ] Test warning message displays with warning icon
4. [ ] Test error/alert message displays with error icon
5. [ ] Test close "×" button works
6. [ ] Test auto-dismiss for info/ok/warning (5 seconds)
7. [ ] Test error messages do NOT auto-dismiss
8. [ ] Test multiple messages display correctly

**Acceptance Criteria**:
- [ ] All message types have appropriate icons
- [ ] Close button is minimal "×" style
- [ ] Auto-dismiss works for info/ok/warning
- [ ] Errors require manual dismiss
- [ ] Smooth animations maintained
- [ ] All tests passing

**Implementation Notes**:
- **Superseded**: Flash messages are being migrated from the Alpine.js `#messages` system to iziToast (see `migrate-flash-messages.md`). Once that migration is complete, icons, auto-dismiss, and close button behaviour will be configured via iziToast options rather than template changes. The tasks above apply only if the Alpine.js system is retained.
- Icons: Use Heroicons or inline SVG
  - Info: `ℹ️` or info circle icon
  - Success/Ok: `✓` or checkmark icon
  - Warning: `⚠️` or exclamation triangle
  - Error/Alert: `✕` or x-circle icon
- Close button: Change from `<button class="button button-xs">Ok</button>` to `<button class="text-gray-500 hover:text-gray-700">&times;</button>`
- Auto-dismiss: Add `x-init="setTimeout(() => { show = false; removeMessage($el.closest('li'), 'info') }, 5000)"` for info/ok/warning
- Keep existing Alpine.js logic and transitions
- Colors already correct (green, yellow, red, blue)

---

## Step 5: Add Breadcrumb Navigation

**Files**:
- `app/ui/common/breadcrumbs.py` (new)
- `app/ui/templates/layout/base.html.j2`
- `app/ui/templates/layout/breadcrumbs.html.j2` (new) *(completed)*
- All deep page templates (upload view, profile, etc.)

**Tasks**:
1. [x] Create breadcrumb context processor in `app/ui/common/breadcrumbs.py`
2. [x] Implement router-level `Breadcrumbs` handler with per-request factory pattern
3. [x] Create breadcrumb component template
4. [x] Add breadcrumbs to deep pages only (not home/top-level) *(gallery/random and gallery/index)*
5. [x] Style breadcrumbs with separators *(SVG polygon cap for first, stroked chevron for subsequent)*
6. [ ] Make breadcrumbs responsive (truncate on mobile)
7. [ ] Add structured data for SEO (schema.org BreadcrumbList)
8. [x] Ensure last item is not a link (current page shown bold, not linked)

**Tests**:
1. [ ] Test breadcrumbs NOT on home page
2. [ ] Test breadcrumbs on profile page (Home → Profile)
3. [ ] Test breadcrumbs on upload view page (Home → View → Upload Title)
4. [ ] Test breadcrumbs on upload page (Home → Upload)
5. [ ] Test breadcrumb links work
6. [ ] Test mobile truncation
7. [ ] Test structured data present

**Acceptance Criteria**:
- [ ] Breadcrumbs on deep pages only
- [ ] Links functional
- [ ] Responsive design
- [ ] SEO optimized
- [ ] All tests passing

**Implementation Notes**:
- **Context Processor Approach**: Create `get_breadcrumbs()` function that auto-generates from route
- Format: Home → Profile → Upload Title
- Separator: `/` or `>` or chevron icon (`›`)
- Current page: not linked, different styling (bold or different color)
- Mobile: Show only last 2 items with ellipsis (`... → Current Page`)
- Schema.org: Use BreadcrumbList JSON-LD in component
- Only show breadcrumbs if depth > 1 (omit from top-level pages like home)
- Pass breadcrumb data from view to template via context processor
- Example: `breadcrumbs = [{"label": "Home", "url": "/"}, {"label": "Profile", "url": None}]`

---

## Step 6: Update Footer with Version and Links

**Files**: 
- `app/ui/templates/layout/base.html.j2` (footer already exists, needs updates)
- `app/lib/config.py` (add version helper function)
- `app/lib/helpers.py` (or new file for version logic)

**Tasks**:
1. [ ] Create `get_app_version()` helper function with git-based logic
2. [ ] Add version display to footer
3. [ ] Add links to static pages (About, Privacy, Terms, Contact)
4. [ ] Update copyright year to be dynamic
5. [ ] Ensure footer remains sticky to bottom
6. [ ] Test version display in different scenarios

**Tests**:
1. [ ] Test footer displays on all pages
2. [ ] Test version shows exact tag when on tagged commit
3. [ ] Test version shows `{tag}+git` when after a tag
4. [ ] Test version shows `git` when no tags exist
5. [ ] Test version shows hardcoded fallback when `.git` missing
6. [ ] Test all footer links work
7. [ ] Test footer sticks to bottom on short pages
8. [ ] Test responsive layout

**Acceptance Criteria**:
- [ ] Footer on all pages with version info
- [ ] Git-based version logic working
- [ ] All links functional
- [ ] Sticky footer works
- [ ] Responsive design
- [ ] All tests passing

**Implementation Notes**:
- **Current State**: Footer already exists with copyright and GitHub link
- **Version Logic**:
  - Exact tag match: `git describe --exact-match --tags` → Display tag (e.g., `v0.1.0`)
  - After tag: `git describe --tags` + `git rev-parse --short HEAD` → Display `{last_tag}+git+{short_git_hash}` (e.g., `v0.1.0+git+a1b2c3d`)
  - No tags: `git rev-parse --short HEAD` → Display `git+{short_git_hash}` (e.g., `git+a1b2c3d`)
  - No `.git` directory: Read from `app/lib/config.py` hardcoded `APP_VERSION` (set at release tagging time)
- Do NOT allow override via environment variable
- Add to footer: `<span class="text-xs text-gray-500">v{{ app_version }}</span>`
- Links: About (`/about`), Privacy (`/privacy`), Terms (`/terms`), Contact (`/contact`)
- Copyright: `© {{ current_year }} pyupload` (use `datetime.now().year`)
- Footer already sticky with flexbox (`min-h-screen` on wrapper)

---

## Step 7: Implement Gallery Discovery Pages

**Files**:
- `app/ui/gallery.py` *(completed - /random route; /popular and /all added with known bugs)*
- `app/ui/templates/gallery/random.html.j2` *(deleted - reuses gallery/index.html.j2)*
- `app/ui/main.py` *(completed - /random redirect; /popular and /all root aliases added)*
- `app/ui/common/gallery.py` *(completed - RandomGalleryPaginationParams)*
- `app/models/common/pagination.py` *(completed - infinite_scroll field)*

**Tasks**:
1. [x] Create gallery router (`app/ui/gallery.py`) *(random endpoint implemented)*
2. [x] Implement `/random` - Seeded-shuffle paginated random gallery with infinite scroll *(deviates from original plan — see implementation notes)*
3. [x] Implement `/popular` - Most viewed public uploads, standard pagination
4. [x] Implement `/all` - Alphabetical by description, infinite scroll *(deviates from original plan — intentionally differentiated from home/browse)*
5. [x] Reuse gallery grid component from home page *(using gallery/index.html.j2)*
6. [x] Add pagination to random page *(infinite scroll with stable seeded shuffle)*
7. [x] Register router in main.py *(router registered; root-level /popular and /all aliases added)*

**Tests**:
1. [x] Test `/random` returns 200 with empty grid when no uploads exist
2. [x] Test `/random` shows only public uploads to anonymous users
3. [x] Test `/random` response includes infinite scroll trigger
4. [x] Test `/random` response includes `ps` seed input
5. [x] Test page 2 with same `ps` seed does not overlap with page 1
6. [x] Test `/popular` displays most viewed uploads
7. [x] Test `/popular` pagination works
8. [x] Test `/all` displays latest uploads (alphabetical)
9. [x] Test `/all` pagination works (infinite scroll)

**Acceptance Criteria**:
- [x] All three gallery pages functional
- [x] `/random` shows a stable-shuffled paginated grid with infinite scroll
- [x] `/popular` and `/all` show paginated grids
- [x] Only public uploads displayed on `/random`
- [x] All tests passing

**Implementation Notes**:
- `/random` (as implemented): Fetches up to 100,000 public upload IDs, applies a seeded shuffle via `random.Random(seed)`, slices the result for the requested page, then queries those uploads ordered by `created_at` desc. The seed is generated fresh on first load and preserved across infinite-scroll page requests via a hidden `input[name="ps"]` field.
- `/random` (original plan): Was intended to redirect to a single random upload view. This was changed during implementation to a more useful paginated discovery experience.
- `RandomGalleryPaginationParams` in `app/ui/common/gallery.py` holds the `seed` field (alias `ps`) and seed-generation logic, keeping it isolated from the base `PaginationParams`.
- `infinite_scroll: bool = False` added to `PaginationParams` base — any paginated view can opt in; the pagination component switches between infinite scroll and standard page controls based on this flag.
- `/popular`: `Upload.filter(private=0).order_by('-viewed').prefetch_related('images', 'user')`
- `/all`: Same query as home page (latest public uploads)
- Page size: 24 items (consistent with home page)

**Dependencies**:
- Home gallery implementation (reuse components)

---

## Step 8: Create Static Content Pages

**Files**: 
- `app/ui/static_pages.py` (new router)
- `app/ui/templates/static/about.html.j2` (new)
- `app/ui/templates/static/privacy.html.j2` (new)
- `app/ui/templates/static/terms.html.j2` (new)
- `app/ui/templates/static/contact.html.j2` (new)
- `app/ui/main.py` (register router)

**Tasks**:
1. [ ] Create static pages router (`app/ui/static_pages.py`)
2. [ ] Create About page (`/about`) - Project description, features, tech stack
3. [ ] Create Privacy Policy page (`/privacy`) - Data collection, cookies, user data handling
4. [ ] Create Terms of Service page (`/terms`) - Usage terms, liability, content policy
5. [ ] Create Contact page (`/contact`) - Contact information or form
6. [ ] Style pages consistently with site theme
7. [ ] Register router in main.py

**Tests**:
1. [ ] Test `/about` page renders
2. [ ] Test `/privacy` page renders
3. [ ] Test `/terms` page renders
4. [ ] Test `/contact` page renders
5. [ ] Test all pages accessible to anonymous users
6. [ ] Test pages have proper headings and structure
7. [ ] Test responsive design

**Acceptance Criteria**:
- [ ] All four static pages created
- [ ] Content is clear and informative
- [ ] Consistent styling
- [ ] Accessible to all users
- [ ] All tests passing

**Implementation Notes**:
- About: Describe pyupload, mention simplegallery legacy, list features, tech stack
- Privacy: Explain fingerprinting for auto-accounts, no IP logging, cookie usage, data retention (90-day abandonment)
- Terms: Usage guidelines, content policy, liability disclaimers, account types
- Contact: Link to GitHub issues, or simple contact form (email submission)
- Use simple, clear language
- Add breadcrumbs to these pages (Home → About, etc.)
- Consider adding last updated date to Privacy and Terms

**Dependencies**:
- Step 6 (footer links point to these pages)

---

## Step 9: Improve Form Styling and Validation

**Files**: 
- `app/ui/templates/auth/login.html.j2`
- `app/ui/templates/auth/register.html.j2`
- `app/ui/templates/uploads/index.html.j2`
- `app/ui/templates/components/form-field.html.j2` (new)

**Tasks**:
1. [ ] Re-establish global anchor `<a>` base styles (removed during CSS refactor on `implement-upload-view-page` branch; affects links throughout the site)
2. [ ] Create reusable form field component
3. [ ] Add consistent styling to all form inputs
4. [ ] Add validation error display
5. [ ] Add success states for valid inputs
6. [ ] Add focus states and transitions
7. [ ] Add help text for complex fields
8. [ ] Ensure forms are keyboard accessible

**Tests**:
1. [ ] Test form field component renders
2. [ ] Test validation errors display
3. [ ] Test success states display
4. [ ] Test focus states work
5. [ ] Test help text displays
6. [ ] Test keyboard navigation
7. [ ] Test on all forms

**Acceptance Criteria**:
- [ ] Consistent form styling
- [ ] Clear validation feedback
- [ ] Good user experience
- [ ] Keyboard accessible
- [ ] All tests passing

**Implementation Notes**:
- Use Tailwind form plugin for base styles
- Error state: red border, red text, error icon
- Success state: green border, checkmark icon
- Focus: blue ring with transition
- Help text: gray text below input
- Label: bold, above input
- Required fields: asterisk or indicator

---

## Step 10: Accessibility and Polish

**Files**: 
- All templates
- `app/static/css/` (if needed)

**Tasks**:
1. [ ] Add Open Graph meta tags to upload view page (`og:title`, `og:image`, `og:url`, `og:description`)
2. [ ] Run accessibility audit (Lighthouse, axe)
3. [ ] Fix all accessibility issues
4. [ ] Ensure proper heading hierarchy
5. [ ] Add skip to content link
6. [ ] Ensure sufficient color contrast
7. [ ] Test with keyboard only
8. [ ] Test with screen reader
9. [ ] Add focus visible styles

**Tests**:
1. [ ] Test Lighthouse accessibility score (>90)
2. [ ] Test keyboard navigation on all pages
3. [ ] Test screen reader compatibility
4. [ ] Test color contrast ratios
5. [ ] Test focus indicators visible
6. [ ] Test skip link works
7. [ ] Test heading hierarchy

**Acceptance Criteria**:
- [ ] WCAG 2.1 AA compliant
- [ ] Lighthouse score >90
- [ ] Keyboard navigable
- [ ] Screen reader friendly
- [ ] All tests passing

**Implementation Notes**:
- Use semantic HTML elements
- Add ARIA labels where needed
- Ensure focus visible with ring utilities
- Skip link: Hidden until focused, jumps to main content
- Color contrast: Use WebAIM contrast checker
- Heading hierarchy: h1 → h2 → h3 (no skipping)
- Test with NVDA (Windows) or VoiceOver (Mac)

**Dependencies**:
- All previous steps should be complete

---

## Step 11: Integration Testing and Documentation

**Files**: 
- `tests/ui/test_navigation.py` (new)
- `tests/ui/test_accessibility.py` (new)
- `README.md`
- `docs/ui-components.md` (new)

**Tasks**:
1. [ ] Create comprehensive UI tests
2. [ ] Test all navigation flows
3. [ ] Test all user interactions
4. [ ] Test responsive design at all breakpoints
5. [ ] Document all UI components
6. [ ] Create style guide
7. [ ] Update README with screenshots

**Tests**:
1. [ ] Integration test: Full navigation flow
2. [ ] Integration test: User authentication flow
3. [ ] Integration test: Mobile navigation
4. [ ] Test all responsive breakpoints
5. [ ] Test all interactive components
6. [ ] Test accessibility compliance

**Acceptance Criteria**:
- [ ] All integration tests passing
- [ ] All components documented
- [ ] Style guide created
- [ ] README updated
- [ ] Ready for production

**Implementation Notes**:
- Use pytest for testing
- Document component props and usage
- Include code examples in documentation
- Add screenshots to README
- Consider creating Storybook for components (future)

**Dependencies**:
- All previous steps must be complete
