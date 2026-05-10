# Implementation Plan: Upload Pile Preview

## Overview

Tag cards currently display a small dashed-border placeholder with just the tag name. This plan replaces that placeholder with a "pile of photos" visual motif — stacked thumbnails from the tag's uploads — to help visually differentiate cards at a glance. The component is designed to be reusable for collections and any future entity that groups uploads.

### Scope

- New `Tag.get_preview_uploads()` classmethod
- `tags_index_get` updated to provide preview upload data to the template
- New reusable Jinja2 macro `components/common/upload-pile.html.j2`
- Tag card template updated to use the pile component
- Hover spread animation via `input.css`
- Non-image uploads included in piles using a styled extension placeholder card

### Current State

- Tag cards display a `w-16 h-16` dashed-border anchor with the tag name as a placeholder
- `TagSerializer` has no upload data
- `tags_index_get` fetches tags only; no upload prefetch

### Target State

- Tag cards display a stacked pile of up to 5 upload thumbnails/placeholders
- Pile container aspect ratio is derived from the topmost card, clamped to the range 16:9–9:16
- Each card's rotation is deterministic but visually varied (derived from `upload.id`)
- Non-image uploads appear in piles as styled extension placeholder cards
- Pile fans out on hover via CSS nth-child animation
- The pile macro is reusable by collections and other grouping entities without modification

---

## Step 1: Data Layer — Preview Uploads per Tag

**Files**: `app/models/tags.py`

**Tasks**:
1. [ ] Add `Tag.get_preview_uploads(tags: list[Tag], limit: int = 5) -> dict[int, list[Upload]]` classmethod
2. [ ] For each tag instance, query via the M2M reverse relation, prefetch `images`, order by `id`, limit to `limit`
3. [ ] Return a dict keyed by `tag.id`; values are lists of Upload model instances of any file type

**Tests**:
1. [ ] Tag with 5+ uploads returns exactly `limit` uploads
2. [ ] Tag with fewer than `limit` uploads returns all available
3. [ ] Tag with a mix of image and non-image uploads returns both types
4. [ ] Tag with no uploads returns an empty list
5. [ ] Multiple tags handled correctly in a single call

**Acceptance Criteria**:
- [ ] Method returns correct upload counts per tag
- [ ] Both image and non-image uploads are included
- [ ] Method accepts a list of `Tag` model instances and returns `dict[int, list[Upload]]`

**Implementation Notes**:
- Use the existing M2M reverse relation accessor (`tag.uploads.all()...`) — the same accessor already used in `remove_tag_from_upload` — rather than a cross-model filter query
- Run one query per tag (N queries); acceptable for current scale

---

## Step 2: View Layer — Preview Uploads in Tag Context

**Files**: `app/ui/tags.py`

**Tasks**:
1. [ ] Evaluate `await Tag.all()` to a list of model instances; pass to `TagSerializer.from_queryset()` separately
2. [ ] Call `Tag.get_preview_uploads(tag_model_list, limit=5)` to fetch preview uploads
3. [ ] Serialize each preview upload using `UploadSerializer.from_tortoise_orm()` with context `{"user": current_user}`
4. [ ] Add `tag_previews: dict[int, list[UploadSerializer]]` to the template context

**Tests**:
1. [ ] `tags_index_get` includes `tag_previews` in the template context
2. [ ] Keys in `tag_previews` correspond to tag IDs present in `tags`

**Acceptance Criteria**:
- [ ] Template context includes `tag_previews`
- [ ] Preview uploads include both image and non-image `UploadSerializer` instances with `image` populated

**Implementation Notes**:
- Serialization context `{"user": current_user}` is consistent with existing gallery usage
- Only `images` needs to be prefetched; `UPLOAD_PREFETCH_MODELS` is not required here

---

## Step 3: Reusable Template Component

**Files**: `app/ui/templates/components/common/upload-pile.html.j2` (new)

**Tasks**:
1. [ ] Create Jinja2 macro `render_upload_pile(uploads, max_count=5)`
2. [ ] Derive the pile container's aspect ratio from the topmost card (last item in the sliced list): if it has `.image`, clamp `width/height` to the range 9/16–16/9; otherwise default to 4/3. Apply as an inline `style="aspect-ratio: …"` on the container.
3. [ ] Render each upload as an absolutely-positioned `.pile-card` div with `transition-all duration-200`
4. [ ] Assign each card a rotation class selected from a preset list using `(upload.id * 7) % preset_count`, giving deterministic but visually varied rotations
5. [ ] **Image cards**: render `<img>` using `autoresize_url(200)` with `object-cover`
6. [ ] **Non-image cards**: render a placeholder with a neutral background, the `#material-symbols-outlined-unknown-document` icon, and `upload.dot_ext` label
7. [ ] **Empty state** (no uploads): render a dashed-border placeholder consistent with existing app style

**Tests**:
- Visual component; no automated tests required.

**Acceptance Criteria**:
- [ ] Renders correctly with 0, 1, 2, 3, 4, and 5 uploads
- [ ] Image uploads display a thumbnail; non-image uploads display an extension placeholder
- [ ] Each card carries the `.pile-card` CSS class (required for hover animation)
- [ ] Empty state renders a fallback placeholder
- [ ] Container aspect ratio reflects the topmost card's clamped ratio

**Implementation Notes**:
- Rotation preset list should have 7 entries (prime-like count) so sequential upload IDs do not produce a repeating visual pattern
- Use `autoresize_url(200)` — 200px is sufficient for pile preview size

---

## Step 4: Hover Spread Animation

**Files**: `input.css`

**Tasks**:
1. [ ] Add `@layer components` rules targeting `.upload-pile:hover .pile-card:nth-child(n)` with per-position `transform` values to fan the pile
2. [ ] Ensure the pile container does not clip fanned cards during animation (adjust `overflow` if necessary)
3. [ ] Rebuild Tailwind CSS after changes: `npx @tailwindcss/cli -i input.css -o app/static/css/tailwind.css`

**Tests**:
- Visual only; no automated tests required.

**Acceptance Criteria**:
- [ ] Pile fans out visibly on hover
- [ ] Animation is smooth with no clipping or jumping
- [ ] Cards return to resting state when hover ends

**Implementation Notes**:
- Spread pattern: outer cards (indices 1 and 5) fan furthest; middle card (index 3) stays centred or lifts slightly
- The `transition-all duration-200` on each `.pile-card` (set in Step 3) drives the animation

---

## Step 5: Integrate into Tag Card

**Files**: `app/ui/templates/components/tags/card.html.j2`

**Tasks**:
1. [ ] Import the `render_upload_pile` macro at the top of the template
2. [ ] Replace the existing dashed-border placeholder block with a call to `render_upload_pile`, passing `tag_previews.get(tag.id, [])`

**Tests**:
- Covered by Steps 1–2 tests and manual verification.

**Acceptance Criteria**:
- [ ] Tag cards with uploads display a stacked pile
- [ ] Tag cards with no uploads display the fallback placeholder
- [ ] Existing card metadata (stats, title, date) is unchanged

---

## Verification

1. Rebuild Tailwind CSS after `input.css` changes
2. Start the dev server and navigate to `/tags`
3. Confirm tags with image uploads show a photo pile with varied per-card rotations
4. Confirm tags with non-image uploads show extension placeholder cards within the pile
5. Confirm tags with no uploads show the fallback placeholder
6. Hover over a pile and confirm cards fan out smoothly
7. Confirm thumbnail requests use the `autoresize_url(200)` URL pattern
8. Run `uv run pytest tests/` — all tests pass
