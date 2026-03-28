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
- Gallery multi-select is implemented; the sidebar shows a "Download Archive" split-button with format options (ZIP, TAR.GZ, TAR.ZSTD) but all hrefs are `#` placeholders
- APScheduler is running with cron jobs for token, user, and orphaned-file cleanup
- Steps 1–3 complete: model, migration, config, archive creation library, background job, and cleanup scheduler are all in place

### Target State
- Clicking a format option POSTs via HTMX to a UI route with the selected upload IDs and format
- A `DownloadArchive` DB record is created immediately (status: `pending`) and a one-off APScheduler job is queued
- The POST response is an HTML fragment showing a status indicator that polls a status route via HTMX until `ready`, then shows a download link
- Completed archives also appear on the user's profile page with a download link
- Archives expire after a configurable TTL (default 24 h) and are cleaned up by a scheduler job
- Remaining work: Steps 4–6

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
5. [x] Each file in the archive is stored using `upload.originalname` as the member name
6. [x] Raise `FileNotFoundError` if any source file is missing from disk

**Tests** (`tests/test_lib_file_archive.py`):
1. [x] `__init__` validation: path traversal, archive-is-dir, file-exists without/with overwrite, upload ID mismatch, upload path outside storage, missing upload file
2. [x] `create_archive` dispatch: correct method called for each format, unsupported format raises `NotImplementedError`
3. [x] ZIP: valid archive, correct members, `originalname` as arcnames, content matches source, duplicate names handled
4. [x] TAR.GZ / TAR.BZ2 / TAR.XZ: valid archive, correct members, `originalname` as arcnames, content matches source (parametrized)
5. [x] TAR.ZSTD: valid zstd-compressed tarball, correct members, `originalname` as arcnames

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
- `app/main.py`
- `app/ui/templates/archives/` *(new template directory)*

**Tasks**:
1. [ ] `POST /archives/request` — requires authentication; accepts form body `upload_ids` (comma-separated or repeated field) and `format`; validates that all referenced uploads are visible to the requesting user (public uploads from any user, plus the user's own private uploads); rejects any IDs that are not visible; creates a `DownloadArchive` record (status: `pending`, `expires_at` derived from config TTL); calls `schedule_archive_job`; returns an HTML fragment (HTMX response) containing a status indicator component that polls the status route
2. [ ] `GET /archives/{id}/status` — requires authentication; returns an HTML fragment showing current status for the requesting user's archive; when `ready`, includes a download link; when still `pending`, includes HTMX polling attributes to re-request after a short interval; returns 404 if not found or not owned by the requesting user
3. [ ] `GET /archives/{id}/download` — requires authentication; verifies the archive belongs to the requesting user and that status is `ready` and `expires_at` is in the future; serves the archive file as an attachment via `FileResponse`; returns an appropriate error response if pending, failed, or expired
4. [ ] Register the new router in `app/ui/__init__.py` and `app/main.py`

**Implementation Notes**:
- Visibility rule for Step 4 Task 1: an upload is visible to the requesting user if `private = 0` (public) OR `user_id = requesting_user.id` (own upload, regardless of privacy)

**Tests**:
1. [ ] `POST /archives/request` with a mix of the user's own uploads and other users' public uploads creates a DB record and returns an HTML fragment
2. [ ] `POST /archives/request` rejects upload IDs that are private and not owned by the requesting user
3. [ ] `POST /archives/request` rejects an invalid format value
4. [ ] `GET /archives/{id}/status` returns correct fragment for `pending` and `ready` states
5. [ ] `GET /archives/{id}/status` returns 404 for another user's archive
6. [ ] `GET /archives/{id}/download` serves a file attachment for a `ready` archive
7. [ ] `GET /archives/{id}/download` returns a non-200 response for a pending, failed, or expired archive
8. [ ] `GET /archives/{id}/download` returns 404 for another user's archive
9. [ ] All three routes return 401/redirect to login for unauthenticated requests

**Acceptance Criteria**:
- [ ] Authenticated POST with valid visible upload IDs and format creates a `pending` record and returns a status fragment
- [ ] Status fragment transitions to a download link once the archive is `ready`
- [ ] A `ready` archive can be downloaded as a file attachment

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

**Tasks**:
1. [ ] Update each format `<a>` to trigger an HTMX `POST` to `/archives/request`, sending the current multiselect upload IDs and the chosen format
2. [ ] Target the HTMX response to an appropriate element in the sidebar that will render the returned status fragment (polling indicator or download link)

**Tests**:
1. [ ] Clicking a format option in the gallery with uploads selected issues the correct POST

**Acceptance Criteria**:
- [ ] Clicking a format option triggers archive creation and shows inline status feedback to the user
- [ ] When the archive is ready, a download link is presented in the sidebar

**Dependencies**:
- Step 4 must be complete
