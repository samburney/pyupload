# Implementation Plan: Multi-select Archive Download

## Overview

Allow users to select multiple uploads in the gallery and request a downloadable archive (ZIP, TAR.GZ, or TAR.ZSTD). Archive creation runs as a background job. Users can wait for it to complete or return to their profile page later to download it.

### Scope
- `DownloadArchive` TortoiseORM model and Aerich migration to track archive jobs
- Archive creation library supporting ZIP, TAR.GZ, and TAR.ZSTD formats
- APScheduler one-off job to build archives in the background
- APScheduler cron job to clean up expired archives
- UI routes (HTMX-driven) to request an archive, poll its status, and serve the file
- Profile page section listing the user's pending and ready archives
- Frontend wiring of the existing gallery download button to the new UI routes

### Current State
- Steps 1–4 and 6 complete with all tests passing; Step 5 (profile page) remains
- Remaining work: Step 5

### Target State
- Clicking a format option POSTs via HTMX to a UI route with the selected upload IDs and format
- A `DownloadArchive` DB record is created immediately (status: `pending`) and a one-off APScheduler job is queued
- The POST response is an HTML fragment showing a status indicator that polls a status route via HTMX until `ready`, then shows a download link
- Completed archives also appear on the user's profile page with a download link
- Archives expire after a configurable TTL (default 24 h) and are cleaned up by a scheduler job

### Review Snapshot (2026-03-29)
- Steps 1–4 and 6 complete; all tests green (41/41 in `test_ui_archives.py`, plus existing scheduler/model/archive-lib suites).
- Step 5 (profile page) is the only remaining work.
- Features added beyond original scope:
  - `POST /archives/{id}/cancel` route with `HX-Trigger` sidebar refresh
  - "Reuse existing archive if selection matches": `gallery_handle_selected_upload_post` queries non-expired archives for the current user + sorted `upload_ids` match and passes result to sidebar template
  - `ArchiveFormatsEnum.mimetype` property for `Content-Type` mapping
  - `FileArchive._resolve_arcnames()` for duplicate-safe archive member naming
- Known pre-merge item: hardcoded `selectedIds = ['338', '327']` in `app/static/js/app/gallery/multiselect.js` must be removed before merge (marked with TODO)

---

## Step 1: Model, Configuration, and Migration

**Files**:
- `app/models/download_archives.py` *(new)*
- `app/models/__init__.py`
- `app/lib/config.py`
- Aerich migration (generated)

**Tasks**:
1. [x] Add `archive_ttl_hours` config value to `AppConfig` (env: `ARCHIVE_TTL_HOURS`, default: `24`); validate it is a positive integer
2. [x] Derive `archive_storage_path` as `storage_path / "archives"` in `AppConfig`, creating the directory on startup if absent; also configurable via `ARCHIVE_STORAGE_PATH` env var
    Notes: The duplicate `storage_path` resolution block was refactored into a module-level `_resolve_storage_dir` helper used by both paths.
3. [x] Create `DownloadArchive` model with fields: `id` (UUID PK), `user` (FK → User, CASCADE on delete), `upload_ids` (JSONField — list of Upload IDs), `format` (CharEnumField — `zip`, `tar.gz`, `tar.zstd`, plus aliases), `status` (CharEnumField — `pending`, `processing`, `ready`, `failed`), `archive_path` (CharField — filename relative to `archive_storage_path`, generated at record creation time), and `TimestampMixin`
    Notes: `expires_at` is derived at runtime from `created_at + archive_ttl_hours`; no dedicated DB column. A `processing` status was added to the lifecycle. `archive_path` is generated upfront at record creation using `make_unique_filename("archive_" + make_clean_filename(user.username)) + format_extension` (e.g. `archive_sam_20260327-193717_a1b2c3d4.zip`); the background job writes to this known path and only needs to update `status`.
4. [x] Register the model in `MODEL_MODULES` in `app/models/__init__.py`
5. [x] Generate and apply an Aerich migration

**Tests**:
1. [x] Model can be created and persisted with `pending` status (`test_models_download_archives.py`)
2. [x] Config correctly derives and creates `archive_storage_path` (`test_lib_config.py`)
3. [x] Config raises on invalid `ARCHIVE_TTL_HOURS` value (`test_lib_config.py`)

**Acceptance Criteria**:
- [x] `download_archives` table exists in the database after migration
- [x] `AppConfig` exposes `archive_ttl_hours` and `archive_storage_path`

---

## Step 2: Archive Creation Library

**Files**:
- `app/lib/file_archive.py` *(new)*

**Implementation notes**:
- Implemented as a `FileArchive` class rather than a standalone function, to allow subclassing for future format support
- Signature: `FileArchive(download_archive: DownloadArchive, uploads: list[Upload], overwrite_existing: bool = False)`
- `archive_path` is derived internally as `config.archive_storage_path / Path(download_archive.filename).name` — no path components permitted in `filename`
- Upload source paths are resolved via `make_user_filepath` and checked against `config.storage_path` to prevent traversal
- Upload IDs are validated against `download_archive.upload_ids` using set symmetric difference; mismatch raises `ValueError` with the delta
- Format dispatch via `create_archive()` → `create_{clean_format}_archive()` using `clean_text(format, '')` to normalise enum values; unsupported formats raise `NotImplementedError`
- `tar.gz`, `tar.bz2`, `tar.xz` share `_create_tarball(mode: Literal['w:gz', 'w:bz2', 'w:xz'])`
- `tar.zstd` uses the `zstandard` package, streaming through `ZstdCompressor → tarfile(mode='w|')`; compression level from `config.archive_zstd_level`
- `ArchiveFormatsEnum` extended with `tar.bz2` and `tar.xz` aliases

**Tasks**:
1. [x] Implement `FileArchive` class with `__init__` validation
2. [x] Support `zip` format using Python's stdlib `zipfile`
3. [x] Support `tar.gz`, `tar.bz2`, `tar.xz` formats using Python's stdlib `tarfile`
4. [x] Support `tar.zstd` format using the `zstandard` package — add `zstandard` to project dependencies via `uv`
5. [x] Each file in the archive uses `upload.originalname` as the member name; duplicates disambiguated by `_resolve_arcnames()` with ` (N)` suffix before extension (e.g. `photo.jpg`, `photo (2).jpg`)
6. [x] Raise `FileNotFoundError` if any source file is missing from disk

**Tests** (`tests/test_lib_file_archive.py`):
1. [x] `__init__` validation: path traversal, archive-is-dir, file-exists without/with overwrite, upload ID mismatch, upload path outside storage, missing upload file
2. [x] `create_archive` dispatch: correct method called for each format, unsupported format raises `NotImplementedError`
3. [x] ZIP: valid archive, correct members, `originalname` as arcnames, content matches source, duplicate names deduplicated with ` (N)` suffix
4. [x] TAR.GZ / TAR.BZ2 / TAR.XZ: valid archive, correct members, `originalname` as arcnames, content matches source, duplicate names (parametrized)
5. [x] TAR.ZSTD: valid zstd-compressed tarball, correct members, `originalname` as arcnames, duplicate names
6. [x] `_resolve_arcnames`: no duplicates unchanged, single/triple duplicates get ` (N)` suffix, mixed unique/duplicate, order preserved

**Acceptance Criteria**:
- [x] All formats produce valid, extractable archives containing the correct files
- [x] `zstandard` dependency is present in `pyproject.toml`

---

## Step 3: Background Job and Cleanup Scheduler

**Files**:
- `app/lib/scheduler.py`
- `app/lib/file_archive.py` (cleanup helper)
- `app/models/download_archives.py` (`cleanup_expired` class method)

**Implementation notes**:
- `run_archive_job(download_archive_id: UUID)` — fetches `DownloadArchive` where `status=pending`; marks individual upload lookup failures as `failed`; constructs `FileArchive` and transitions to `processing` before calling `asyncio.to_thread(file_archiver.create_archive)`; on any exception calls `_mark_download_archive_failed` (logs + sets `failed`); on success validates the file exists and is non-empty before setting `ready`
- `_mark_download_archive_failed` is a private async helper that centralises status updates and error logging
- `schedule_archive_job(download_archive_id: UUID, run_date='now')` — calls `scheduler.add_job(func=run_archive_job, trigger='date', run_date=run_date, kwargs={...})`
- `DownloadArchive.cleanup_expired()` — class method; queries records where `created_at < now - archive_max_age_hours`; calls `archive.delete()` on each (the model `delete()` override removes the file from disk via `asyncio.to_thread`)
- `cleanup_orphaned_archives()` — standalone async function in `app/lib/file_archive.py`; globs `archive_storage_path`; skips dot files, directories, and files newer than `archive_max_age_hours`; for each remaining file checks for a matching DB record by `filename`; deletes orphans via `await to_thread(delete_file, file)`
- `cleanup_archives_job()` — scheduler job that calls both `DownloadArchive.cleanup_expired()` and `cleanup_orphaned_archives()`, logging counts for each; registered as hourly cron with jitter

**Tasks**:
1. [x] Implement `async def run_archive_job(download_archive_id: UUID)`
2. [x] Implement `DownloadArchive.cleanup_expired()` class method
3. [x] Implement `async def cleanup_orphaned_archives()` in `app/lib/file_archive.py`
4. [x] Implement `async def cleanup_archives_job()` and register as hourly cron
5. [x] Expose `schedule_archive_job(download_archive_id: UUID)`

**Tests**:
1. [x] `run_archive_job` transitions status `pending` → `processing` → `ready` on success, and the file exists on disk (`test_lib_scheduler.py::TestRunArchiveJob`)
2. [x] `run_archive_job` transitions status to `failed` and logs when `create_archive` raises
3. [x] `run_archive_job` returns early and logs when archive not found or not `pending`
4. [x] `run_archive_job` sets `failed` when referenced upload does not exist
5. [x] `run_archive_job` sets `failed` when archive file is missing or empty after creation
6. [x] `DownloadArchive.cleanup_expired` deletes expired DB records and files from disk; preserves non-expired records; returns correct count (`test_models_download_archives.py::TestDownloadArchiveCleanupExpired`)
7. [x] `cleanup_orphaned_archives` deletes old files with no DB record; skips files with a DB record, new files, dot files, and directories; returns correct count (`test_lib_file_archive.py::TestCleanupOrphanedArchives`)
8. [x] `cleanup_archives_job` calls both cleanup functions and logs counts (`test_lib_scheduler.py::TestCleanupArchivesJob`)

**Acceptance Criteria**:
- [x] A queued job produces a `ready` archive record with a valid file on disk
- [x] Expired archives are removed from both disk and database by the cleanup job

---

## Step 4: UI Routes

**Files**:
- `app/ui/archives.py` *(new)*
- `app/ui/__init__.py`
- `app/ui/templates/components/archive/download-button.html.j2` *(new)*

**Tasks**:
1. [x] `POST /archives/request/{download_format}` — requires authentication; accepts form body `super_selected`, `selected_ids`, `deselected_ids`; filters to uploads readable by the requesting user; creates a `DownloadArchive` record (status: `pending`); calls `schedule_archive_job`; returns an HTML fragment containing a status indicator that polls the status route
2. [x] `GET /archives/{id}/status` — requires authentication; returns updated `download-button.html.j2` fragment showing current status; when `ready`, flashes a message and includes a download link; polls every 2 s while `pending` or `processing`; returns 404 fragment if not found or not owned
3. [x] `GET /archives/{id}/download[/{filename}]` — requires authentication; verifies archive belongs to requesting user and status is `ready`; serves archive file as attachment via `FileResponse` with correct `Content-Disposition` (quoted filename) and `Content-Type` from `ArchiveFormatsEnum.mimetype`; returns error template for pending/failed or missing file
4. [x] `POST /archives/{id}/cancel` — requires authentication; cancels a `pending` archive; returns `HX-Trigger: {"update-sidebar": {}}` on success so the sidebar re-renders
5. [x] Register the new router in `app/ui/__init__.py`

**Implementation Notes**:
- Actual path is `POST /archives/request/{download_format}` (format in path, not form body)
- `upload_ids` stored sorted to enable direct `filter(upload_ids=sorted_list)` lookup for "reuse existing archive" feature
- Cancel route has an intentionally dual branch: the `get_or_none` filter uses `status=pending` now, but `cancel()` checks status independently to allow future expansion to cancel `processing` archives without changing the guard logic
- `ArchiveFormatsEnum.mimetype` property maps enum values to MIME type strings for `Content-Type` header
- "Reuse existing archive" feature lives in `gallery.py` (sidebar context), not in `archives.py` (routes)

**Tests** (`tests/test_ui_archives.py`):
1. [x] `POST /archives/request/{format}` with valid selected IDs creates a DB record and returns an HTML fragment
2. [x] `POST /archives/request/{format}` rejects upload IDs that are private and not owned by the requesting user
3. [x] `POST /archives/request/{format}` rejects an invalid format value
4. [x] `GET /archives/{id}/status` returns correct fragment for `pending` and `ready` states
5. [x] `GET /archives/{id}/status` returns 404 fragment for another user's archive
6. [x] `GET /archives/{id}/download` serves a file attachment for a `ready` archive
7. [x] `GET /archives/{id}/download` returns a non-200 response for a pending, failed, or missing-file archive
8. [x] `GET /archives/{id}/download` returns 404 for another user's archive
9. [x] `POST /archives/{id}/cancel` cancels a pending archive and returns `HX-Trigger` header
10. [x] All routes return 401/redirect to login for unauthenticated requests

**Acceptance Criteria**:
- [x] Authenticated POST with valid upload IDs and format creates a `pending` record and returns a status fragment
- [x] Status fragment transitions to a download link once the archive is `ready`
- [x] A `ready` archive can be downloaded as a file attachment
- [x] Tests written and passing (41/41 passing)

---

## Step 5: Profile Page Integration

**Files**:
- Profile page route (existing, in `app/ui/users.py`)
- Profile page template (existing)
- `app/ui/templates/archives/profile-list.html.j2` *(new)*

**Tasks**:
1. [ ] Query the logged-in user's non-expired `DownloadArchive` records in the profile page route, ordered by `created_at` descending
2. [ ] Add a "Downloads" section to the profile page template that renders the archive list partial; show status badge (`pending`, `ready`, `failed`) and a download link for `ready` archives; omit the section entirely if there are no records

**Tests**:
1. [ ] Profile page renders pending and ready archive entries correctly
2. [ ] Profile page omits the section when no non-expired archives exist
3. [ ] Profile page does not render expired archives

**Acceptance Criteria**:
- [ ] A user can return to their profile page to find and download a previously requested archive
- [ ] Expired and failed archives do not appear

**Dependencies**:
- Step 4 must be complete (download route is linked from this page)

---

## Step 6: Frontend Integration

**Files**:
- `app/ui/templates/components/gallery/download-button.html.j2`
- `app/ui/templates/components/gallery/multiselect-sidebar.html.j2`

**Tasks**:
1. [x] Each format button triggers `hx-post` to `/archives/request/{format}`, including `[name='super_selected']`, `[name='selected_ids']`, `[name='deselected_ids']` form fields via `hx-include`
2. [x] Response targets `#archive-download-button` in the sidebar; 4xx errors target `#messages`
3. [x] `multiselect-sidebar.html.j2` conditionally renders `gallery/download-button.html.j2` (new request) or `archive/download-button.html.j2` (existing/in-progress archive) based on `download_archive` context variable
4. [x] `archive/download-button.html.j2` shows queued/processing/ready/failed states with polling (`hx-trigger="every 2s"`) and cancel button

**Implementation Notes**:
- `download-button.html.j2` also handles the "reuse ready archive" case: if `download_archive` is defined and `ready`, the primary action button becomes a direct download link instead of a POST
- The sidebar shows the existing archive status component (`archive/download-button.html.j2`) whenever `download_archive` is set and not `ready`; once `ready` it reverts to `download-button.html.j2` (which then renders the download link variant)

**Tests** (`tests/test_ui_archives.py::TestMultiselectSidebarRendering`):
1. [x] No existing archive → request button with `hx-post` to `/archives/request/` is rendered
2. [x] Matching pending archive → status component with cancel button is rendered
3. [x] Matching processing archive → status component is rendered
4. [x] Matching ready archive → direct download link is rendered
5. [x] Failed archive excluded → request button is rendered (fresh start)
6. [x] Archive for a different selection does not match → request button rendered

**Acceptance Criteria**:
- [x] Clicking a format option triggers archive creation and shows inline status feedback to the user
- [x] When the archive is ready, a download link is presented in the sidebar
- [x] Tests written and passing (41/41 passing)

**Dependencies**:
- Step 4 must be complete ✓
