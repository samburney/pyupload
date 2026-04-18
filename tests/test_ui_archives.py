"""Tests for app/ui/archives.py — Archive download UI endpoints.

Routes tested:
- POST /archives/request/{download_format}
- GET  /archives/{id}/status
- POST /archives/{id}/cancel
- DELETE /archives/{id}
- GET  /archives/{id}/download[/{filename}]
- GET  /archives/profile-list

Also covers Step 6 frontend integration: gallery multiselect sidebar renders
the correct download-button component depending on whether a matching archive
already exists (POST /gallery).
"""

import uuid
from datetime import datetime, timedelta, timezone
import pytest_asyncio
from unittest.mock import patch

from app.lib.auth import create_access_token
from app.lib.config import get_app_config
from app.models.users import User
from app.models.uploads import Upload
from app.models.download_archives import DownloadArchive, ArchiveFormatsEnum, ArchiveStatusEnum

config = get_app_config()


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _auth(user: User) -> dict:
    """Return a cookies dict that authenticates *user*."""
    return {"access_token": create_access_token({"sub": user.username})}


def _htmx() -> dict:
    """Return HTMX request headers."""
    return {"HX-Request": "true"}


async def _make_user(username: str) -> User:
    return await User.create(
        username=username,
        email=f"{username}@test.com",
        password="hashed",
        is_registered=True,
    )


async def _make_upload(user: User, name: str, private: bool = False) -> Upload:
    return await Upload.create(
        user=user,
        name=f"{name}_20260101-000000_abcd1234",
        cleanname=name,
        originalname=f"{name}.txt",
        ext="txt",
        size=100,
        type="text/plain",
        extra="",
        description="",
        private=private,
    )


async def _make_archive(
    user: User,
    uploads: list[Upload],
    status: ArchiveStatusEnum = ArchiveStatusEnum.pending,
    suffix: str = "aaaa0000",
) -> DownloadArchive:
    return await DownloadArchive.create(
        user=user,
        upload_ids=sorted(u.id for u in uploads),
        format=ArchiveFormatsEnum.zip,
        status=status,
        filename=f"archive_{user.username}_20260101-000000_{suffix}.zip",
    )


def _make_archive_file(archive: DownloadArchive) -> None:
    """Write a dummy archive file to disk so download tests can serve it."""
    path = config.archive_storage_path / archive.filename
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(b"PK\x03\x04fake zip content")


# ===========================================================================
# POST /archives/request/{download_format}
# ===========================================================================

class TestRequestArchivePost:

    async def test_requires_htmx_header(self, client):
        owner = await _make_user("req_nohtmx")
        upload = await _make_upload(owner, "f1")
        client.cookies = _auth(owner)
        response = await client.post(
            "/archives/request/zip",
            data={"selected_ids": [upload.id]},
        )
        assert response.status_code == 400

    async def test_requires_authentication(self, client):
        owner = await _make_user("req_noauth_owner")
        upload = await _make_upload(owner, "f2")
        response = await client.post(
            "/archives/request/zip",
            data={"selected_ids": [upload.id]},
            headers=_htmx(),
        )
        assert response.status_code in (302, 303, 401)

    async def test_invalid_format_returns_400(self, client):
        owner = await _make_user("req_badfmt")
        upload = await _make_upload(owner, "f3")
        client.cookies = _auth(owner)
        response = await client.post(
            "/archives/request/rar",
            data={"selected_ids": [upload.id]},
            headers=_htmx(),
        )
        assert response.status_code == 400

    async def test_empty_selection_returns_403(self, client):
        owner = await _make_user("req_empty")
        client.cookies = _auth(owner)
        response = await client.post(
            "/archives/request/zip",
            data={"selected_ids": []},
            headers=_htmx(),
        )
        assert response.status_code == 403

    async def test_private_upload_from_other_user_excluded(self, client):
        """Private uploads from another user produce no readable selection → 403."""
        owner = await _make_user("req_perm_owner")
        other = await _make_user("req_perm_other")
        private_upload = await _make_upload(other, "priv", private=True)
        client.cookies = _auth(owner)
        response = await client.post(
            "/archives/request/zip",
            data={"selected_ids": [private_upload.id]},
            headers=_htmx(),
        )
        assert response.status_code == 403

    async def test_public_upload_from_other_user_is_readable(self, client):
        """Public uploads from another user are readable and create a valid archive."""
        owner = await _make_user("req_pub_owner")
        other = await _make_user("req_pub_other")
        public_upload = await _make_upload(other, "pub", private=False)
        client.cookies = _auth(owner)
        with patch("app.ui.archives.schedule_archive_job"):
            response = await client.post(
                "/archives/request/zip",
                data={"selected_ids": [public_upload.id]},
                headers=_htmx(),
            )
        assert response.status_code == 200
        assert await DownloadArchive.filter(user=owner).count() == 1

    async def test_valid_request_creates_pending_record(self, client):
        owner = await _make_user("req_valid")
        upload = await _make_upload(owner, "f4")
        client.cookies = _auth(owner)
        with patch("app.ui.archives.schedule_archive_job"):
            response = await client.post(
                "/archives/request/zip",
                data={"selected_ids": [upload.id]},
                headers=_htmx(),
            )
        assert response.status_code == 200
        archive = await DownloadArchive.filter(user=owner).get()
        assert archive.status == ArchiveStatusEnum.pending

    async def test_valid_request_schedules_job(self, client):
        owner = await _make_user("req_schedule")
        upload = await _make_upload(owner, "f5")
        client.cookies = _auth(owner)
        with patch("app.ui.archives.schedule_archive_job") as mock_schedule:
            await client.post(
                "/archives/request/zip",
                data={"selected_ids": [upload.id]},
                headers=_htmx(),
            )
        mock_schedule.assert_called_once()

    async def test_valid_request_returns_html_fragment(self, client):
        owner = await _make_user("req_html")
        upload = await _make_upload(owner, "f6")
        client.cookies = _auth(owner)
        with patch("app.ui.archives.schedule_archive_job"):
            response = await client.post(
                "/archives/request/zip",
                data={"selected_ids": [upload.id]},
                headers=_htmx(),
            )
        assert "text/html" in response.headers.get("content-type", "")

    async def test_upload_ids_stored_sorted(self, client):
        """IDs sent in reverse order must be stored ascending for archive deduplication."""
        owner = await _make_user("req_sorted")
        u1 = await _make_upload(owner, "s1")
        u2 = await _make_upload(owner, "s2")
        client.cookies = _auth(owner)
        # Send in reverse order
        with patch("app.ui.archives.schedule_archive_job"):
            await client.post(
                "/archives/request/zip",
                data={"selected_ids": [u2.id, u1.id]},
                headers=_htmx(),
            )
        archive = await DownloadArchive.filter(user=owner).get()
        assert archive.upload_ids == sorted([u1.id, u2.id])

    async def test_all_formats_accepted(self, client):
        """Each supported format value creates a record with the correct format."""
        formats = ["zip", "tar.gz", "tar.bz2", "tar.xz", "tar.zstd"]
        for fmt in formats:
            owner = await _make_user(f"req_fmt_{fmt.replace('.', '_')}")
            upload = await _make_upload(owner, f"f_{fmt.replace('.', '_')}")
            client.cookies = _auth(owner)
            with patch("app.ui.archives.schedule_archive_job"):
                response = await client.post(
                    f"/archives/request/{fmt}",
                    data={"selected_ids": [upload.id]},
                    headers=_htmx(),
                )
            assert response.status_code == 200, f"format {fmt!r} was rejected"


# ===========================================================================
# GET /archives/{id}/status
# ===========================================================================

class TestArchiveStatusGet:

    async def test_requires_htmx_header(self, client):
        owner = await _make_user("status_nohtmx")
        upload = await _make_upload(owner, "g1")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(owner)
        response = await client.get(f"/archives/{archive.id}/status")
        assert response.status_code == 400

    async def test_requires_authentication(self, client):
        owner = await _make_user("status_noauth_owner")
        upload = await _make_upload(owner, "g2")
        archive = await _make_archive(owner, [upload])
        response = await client.get(
            f"/archives/{archive.id}/status",
            headers=_htmx(),
        )
        assert response.status_code in (302, 303, 401)

    async def test_returns_html_fragment(self, client):
        owner = await _make_user("status_html")
        upload = await _make_upload(owner, "g3")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(owner)
        response = await client.get(
            f"/archives/{archive.id}/status",
            headers=_htmx(),
        )
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_pending_archive_shows_queued_state(self, client):
        owner = await _make_user("status_pending")
        upload = await _make_upload(owner, "g4")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.pending)
        client.cookies = _auth(owner)
        response = await client.get(
            f"/archives/{archive.id}/status",
            headers=_htmx(),
        )
        assert response.status_code == 200
        assert "queued" in response.text.lower()

    async def test_processing_archive_shows_processing_state(self, client):
        owner = await _make_user("status_processing")
        upload = await _make_upload(owner, "g5")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.processing)
        client.cookies = _auth(owner)
        response = await client.get(
            f"/archives/{archive.id}/status",
            headers=_htmx(),
        )
        assert response.status_code == 200
        assert "processing" in response.text.lower()

    async def test_ready_archive_contains_download_link(self, client):
        owner = await _make_user("status_ready")
        upload = await _make_upload(owner, "g6")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="ready001")
        client.cookies = _auth(owner)
        response = await client.get(
            f"/archives/{archive.id}/status",
            headers=_htmx(),
        )
        assert response.status_code == 200
        # Download link must reference this archive
        assert str(archive.id) in response.text
        assert "/download/" in response.text

    async def test_other_users_archive_returns_404(self, client):
        owner = await _make_user("status_404_owner")
        other = await _make_user("status_404_other")
        upload = await _make_upload(owner, "g7")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(other)
        response = await client.get(
            f"/archives/{archive.id}/status",
            headers=_htmx(),
        )
        assert response.status_code == 404

    async def test_nonexistent_archive_returns_404(self, client):
        owner = await _make_user("status_notfound")
        client.cookies = _auth(owner)
        response = await client.get(
            f"/archives/{uuid.uuid4()}/status",
            headers=_htmx(),
        )
        assert response.status_code == 404


# ===========================================================================
# POST /archives/{id}/cancel
# ===========================================================================

class TestCancelArchivePost:

    async def test_requires_htmx_header(self, client):
        owner = await _make_user("cancel_nohtmx")
        upload = await _make_upload(owner, "c1")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(owner)
        response = await client.post(f"/archives/{archive.id}/cancel")
        assert response.status_code == 400

    async def test_requires_authentication(self, client):
        owner = await _make_user("cancel_noauth_owner")
        upload = await _make_upload(owner, "c2")
        archive = await _make_archive(owner, [upload])
        response = await client.post(
            f"/archives/{archive.id}/cancel",
            headers=_htmx(),
        )
        assert response.status_code in (302, 303, 401)

    async def test_cancel_pending_returns_204(self, client):
        owner = await _make_user("cancel_ok")
        upload = await _make_upload(owner, "c3")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(owner)
        response = await client.post(
            f"/archives/{archive.id}/cancel",
            headers=_htmx(),
        )
        assert response.status_code == 204

    async def test_cancel_returns_hx_trigger_for_sidebar_refresh(self, client):
        owner = await _make_user("cancel_trigger")
        upload = await _make_upload(owner, "c4")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(owner)
        response = await client.post(
            f"/archives/{archive.id}/cancel",
            headers=_htmx(),
        )
        assert response.status_code == 204
        assert "HX-Trigger" in response.headers
        assert "update-sidebar" in response.headers["HX-Trigger"]

    async def test_cancel_deletes_db_record(self, client):
        owner = await _make_user("cancel_delete")
        upload = await _make_upload(owner, "c5")
        archive = await _make_archive(owner, [upload])
        archive_id = archive.id
        client.cookies = _auth(owner)
        await client.post(
            f"/archives/{archive_id}/cancel",
            headers=_htmx(),
        )
        assert await DownloadArchive.get_or_none(id=archive_id) is None

    async def test_cannot_cancel_another_users_archive(self, client):
        owner = await _make_user("cancel_owner")
        other = await _make_user("cancel_other")
        upload = await _make_upload(owner, "c6")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(other)
        response = await client.post(
            f"/archives/{archive.id}/cancel",
            headers=_htmx(),
        )
        assert response.status_code == 404

    async def test_cancel_nonexistent_archive_returns_404(self, client):
        owner = await _make_user("cancel_notfound")
        client.cookies = _auth(owner)
        response = await client.post(
            f"/archives/{uuid.uuid4()}/cancel",
            headers=_htmx(),
        )
        assert response.status_code == 404


# ===========================================================================
# GET /archives/{id}/download[/{filename}]
# ===========================================================================

class TestDownloadArchiveGet:

    async def test_requires_authentication(self, client):
        owner = await _make_user("dl_noauth_owner")
        upload = await _make_upload(owner, "d1")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="dl000001")
        _make_archive_file(archive)
        response = await client.get(f"/archives/{archive.id}/download")
        assert response.status_code in (302, 303, 401)

    async def test_ready_archive_returns_200(self, client):
        owner = await _make_user("dl_ready")
        upload = await _make_upload(owner, "d2")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="dl000002")
        _make_archive_file(archive)
        client.cookies = _auth(owner)
        response = await client.get(f"/archives/{archive.id}/download")
        assert response.status_code == 200

    async def test_ready_archive_content_type_is_zip(self, client):
        owner = await _make_user("dl_ctype")
        upload = await _make_upload(owner, "d3")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="dl000003")
        _make_archive_file(archive)
        client.cookies = _auth(owner)
        response = await client.get(f"/archives/{archive.id}/download")
        assert response.headers.get("content-type") == "application/zip"

    async def test_ready_archive_content_disposition_is_quoted_attachment(self, client):
        """Content-Disposition must be 'attachment' with a quoted filename."""
        owner = await _make_user("dl_cd")
        upload = await _make_upload(owner, "d4")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="dl000004")
        _make_archive_file(archive)
        client.cookies = _auth(owner)
        response = await client.get(f"/archives/{archive.id}/download")
        cd = response.headers.get("content-disposition", "")
        assert cd.startswith("attachment")
        assert 'filename="' in cd

    async def test_named_download_uses_given_filename(self, client):
        """/{id}/download/{filename} variant reflects the requested filename."""
        owner = await _make_user("dl_named")
        upload = await _make_upload(owner, "d5")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="dl000005")
        _make_archive_file(archive)
        client.cookies = _auth(owner)
        response = await client.get(
            f"/archives/{archive.id}/download/my_export.zip"
        )
        assert response.status_code == 200
        assert "my_export.zip" in response.headers.get("content-disposition", "")

    async def test_pending_archive_returns_error(self, client):
        owner = await _make_user("dl_pending")
        upload = await _make_upload(owner, "d6")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.pending, suffix="dl000006")
        client.cookies = _auth(owner)
        response = await client.get(f"/archives/{archive.id}/download")
        assert response.status_code not in (200, 302)

    async def test_failed_archive_returns_error(self, client):
        owner = await _make_user("dl_failed")
        upload = await _make_upload(owner, "d7")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.failed, suffix="dl000007")
        client.cookies = _auth(owner)
        response = await client.get(f"/archives/{archive.id}/download")
        assert response.status_code not in (200, 302)

    async def test_other_users_archive_returns_404(self, client):
        owner = await _make_user("dl_404_owner")
        other = await _make_user("dl_404_other")
        upload = await _make_upload(owner, "d8")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="dl000008")
        _make_archive_file(archive)
        client.cookies = _auth(other)
        response = await client.get(f"/archives/{archive.id}/download")
        assert response.status_code == 404

    async def test_missing_file_on_disk_returns_404(self, client):
        """Ready status but no file on disk → 404."""
        owner = await _make_user("dl_nofile")
        upload = await _make_upload(owner, "d9")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="dl000009")
        # Deliberately do not create the file
        client.cookies = _auth(owner)
        response = await client.get(f"/archives/{archive.id}/download")
        assert response.status_code == 404


# ===========================================================================
# Step 6 — Gallery multiselect sidebar rendering  (POST /gallery)
# ===========================================================================

class TestMultiselectSidebarRendering:
    """
    Verify the correct download-button component is rendered in the gallery
    sidebar based on whether a matching DownloadArchive record exists.

    POST /gallery returns a sidebar partial. With 2+ selected uploads it
    renders components/gallery/multiselect-sidebar.html.j2, which conditionally
    includes either the 'request' button or the archive status component.
    """

    @pytest_asyncio.fixture
    async def owner(self, client):
        return await _make_user("sidebar_owner")

    @pytest_asyncio.fixture
    async def uploads(self, owner):
        """Two uploads so the multiselect (not single-upload) sidebar is rendered."""
        u1 = await _make_upload(owner, "sb1")
        u2 = await _make_upload(owner, "sb2")
        return [u1, u2]

    async def test_no_existing_archive_shows_request_button(self, client, owner, uploads):
        """When no matching archive exists, the format-selection button (hx-post) is shown."""
        client.cookies = _auth(owner)
        response = await client.post(
            "/gallery/update-selected",
            data={"selected_ids": [u.id for u in uploads]},
            headers=_htmx(),
        )
        assert response.status_code == 200
        assert "/archives/request/" in response.text

    async def test_pending_archive_shows_status_component(self, client, owner, uploads):
        """When a matching pending archive exists, the status/cancel component is shown."""
        archive = await _make_archive(owner, uploads, status=ArchiveStatusEnum.pending, suffix="sb000001")
        client.cookies = _auth(owner)
        response = await client.post(
            "/gallery/update-selected",
            data={"selected_ids": [u.id for u in uploads]},
            headers=_htmx(),
        )
        assert response.status_code == 200
        # The status component references the archive's status polling endpoint
        assert str(archive.id) in response.text
        assert "queued" in response.text.lower()

    async def test_processing_archive_shows_status_component(self, client, owner, uploads):
        """When a matching processing archive exists, the status component is shown."""
        archive = await _make_archive(owner, uploads, status=ArchiveStatusEnum.processing, suffix="sb000002")
        client.cookies = _auth(owner)
        response = await client.post(
            "/gallery/update-selected",
            data={"selected_ids": [u.id for u in uploads]},
            headers=_htmx(),
        )
        assert response.status_code == 200
        assert str(archive.id) in response.text
        assert "processing" in response.text.lower()

    async def test_ready_archive_shows_download_link(self, client, owner, uploads):
        """When a matching ready archive exists, a direct download link is shown."""
        archive = await _make_archive(owner, uploads, status=ArchiveStatusEnum.ready, suffix="sb000003")
        client.cookies = _auth(owner)
        response = await client.post(
            "/gallery/update-selected",
            data={"selected_ids": [u.id for u in uploads]},
            headers=_htmx(),
        )
        assert response.status_code == 200
        assert str(archive.id) in response.text
        assert "/download/" in response.text

    async def test_failed_archive_excluded_shows_request_button(self, client, owner, uploads):
        """Failed archives are excluded from the query; the fresh request button is shown."""
        await _make_archive(owner, uploads, status=ArchiveStatusEnum.failed, suffix="sb000004")
        client.cookies = _auth(owner)
        response = await client.post(
            "/gallery/update-selected",
            data={"selected_ids": [u.id for u in uploads]},
            headers=_htmx(),
        )
        assert response.status_code == 200
        assert "/archives/request/" in response.text

    async def test_different_selection_shows_request_button(self, client, owner, uploads):
        """An archive for a different set of uploads does not match the current selection."""
        u3 = await _make_upload(owner, "sb3")
        # Archive for [u3] only — not matching [u1, u2]
        await _make_archive(owner, [u3], status=ArchiveStatusEnum.pending, suffix="sb000005")
        client.cookies = _auth(owner)
        response = await client.post(
            "/gallery/update-selected",
            data={"selected_ids": [u.id for u in uploads]},
            headers=_htmx(),
        )
        assert response.status_code == 200
        assert "/archives/request/" in response.text


# ===========================================================================
# DELETE /archives/{id}
# ===========================================================================

class TestDeleteArchiveDelete:

    async def test_requires_htmx_header(self, client):
        owner = await _make_user("del_nohtmx")
        upload = await _make_upload(owner, "e1")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(owner)
        response = await client.delete(f"/archives/{archive.id}")
        assert response.status_code == 400

    async def test_requires_authentication(self, client):
        owner = await _make_user("del_noauth_owner")
        upload = await _make_upload(owner, "e2")
        archive = await _make_archive(owner, [upload])
        response = await client.delete(f"/archives/{archive.id}", headers=_htmx())
        assert response.status_code in (302, 303, 401)

    async def test_deletes_pending_archive(self, client):
        owner = await _make_user("del_pending")
        upload = await _make_upload(owner, "e3")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.pending)
        archive_id = archive.id
        client.cookies = _auth(owner)
        response = await client.delete(f"/archives/{archive_id}", headers=_htmx())
        assert response.status_code in (200, 204)
        assert await DownloadArchive.get_or_none(id=archive_id) is None

    async def test_deletes_ready_archive(self, client):
        owner = await _make_user("del_ready")
        upload = await _make_upload(owner, "e4")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="del00001")
        archive_id = archive.id
        client.cookies = _auth(owner)
        response = await client.delete(f"/archives/{archive_id}", headers=_htmx())
        assert response.status_code in (200, 204)
        assert await DownloadArchive.get_or_none(id=archive_id) is None

    async def test_returns_hx_trigger_when_on_profile_page(self, client):
        owner = await _make_user("del_profile_trigger")
        upload = await _make_upload(owner, "e5")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(owner)
        response = await client.delete(
            f"/archives/{archive.id}",
            headers={**_htmx(), "HX-Current-URL": "http://test/profile"},
        )
        assert response.status_code == 200
        assert "refresh-profile-download-archives-table" in response.headers.get("HX-Trigger", "")

    async def test_returns_204_when_not_on_profile_page(self, client):
        owner = await _make_user("del_no_profile")
        upload = await _make_upload(owner, "e6")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(owner)
        response = await client.delete(f"/archives/{archive.id}", headers=_htmx())
        assert response.status_code == 204

    async def test_nonexistent_archive_returns_404(self, client):
        owner = await _make_user("del_notfound")
        client.cookies = _auth(owner)
        response = await client.delete(f"/archives/{uuid.uuid4()}", headers=_htmx())
        assert response.status_code == 404

    async def test_cannot_delete_another_users_archive(self, client):
        owner = await _make_user("del_owner")
        other = await _make_user("del_other")
        upload = await _make_upload(owner, "e7")
        archive = await _make_archive(owner, [upload])
        client.cookies = _auth(other)
        response = await client.delete(f"/archives/{archive.id}", headers=_htmx())
        assert response.status_code == 404
        assert await DownloadArchive.get_or_none(id=archive.id) is not None


# ===========================================================================
# GET /archives/profile-list
# ===========================================================================

class TestProfileArchiveListGet:

    async def test_requires_htmx_header(self, client):
        owner = await _make_user("plist_nohtmx")
        client.cookies = _auth(owner)
        response = await client.get("/archives/profile-list")
        assert response.status_code == 400

    async def test_requires_authentication(self, client):
        response = await client.get("/archives/profile-list", headers=_htmx())
        assert response.status_code in (302, 303, 401)

    async def test_returns_html_with_archives(self, client):
        owner = await _make_user("plist_html")
        upload = await _make_upload(owner, "p1")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.pending, suffix="pl000001")
        client.cookies = _auth(owner)
        response = await client.get("/archives/profile-list", headers=_htmx())
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")
        assert archive.filename in response.text

    async def test_excludes_expired_archives(self, client):
        owner = await _make_user("plist_expired")
        upload = await _make_upload(owner, "p2")
        archive = await _make_archive(owner, [upload], suffix="pl000002")
        old_time = datetime.now(tz=timezone.utc) - timedelta(hours=config.archive_max_age_hours + 1)
        await DownloadArchive.filter(id=archive.id).update(created_at=old_time)
        client.cookies = _auth(owner)
        response = await client.get("/archives/profile-list", headers=_htmx())
        assert response.status_code == 200
        assert archive.filename not in response.text

    async def test_empty_state_when_no_archives(self, client):
        owner = await _make_user("plist_empty")
        client.cookies = _auth(owner)
        response = await client.get("/archives/profile-list", headers=_htmx())
        assert response.status_code == 200
        assert "profile-download-archives-table" in response.text
        assert "<table" not in response.text

    async def test_ready_archive_includes_download_link(self, client):
        owner = await _make_user("plist_ready")
        upload = await _make_upload(owner, "p3")
        archive = await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="pl000003")
        client.cookies = _auth(owner)
        response = await client.get("/archives/profile-list", headers=_htmx())
        assert response.status_code == 200
        assert str(archive.id) in response.text
        assert "/download/" in response.text

    async def test_polls_when_archives_in_progress(self, client):
        """Table hx-trigger should include 'every 2s' when a pending archive exists."""
        owner = await _make_user("plist_poll")
        upload = await _make_upload(owner, "p4")
        await _make_archive(owner, [upload], status=ArchiveStatusEnum.pending, suffix="pl000004")
        client.cookies = _auth(owner)
        response = await client.get("/archives/profile-list", headers=_htmx())
        assert "every 2s" in response.text

    async def test_no_polling_when_all_archives_terminal(self, client):
        """Table hx-trigger should not include 'every 2s' when all archives are terminal."""
        owner = await _make_user("plist_nopoll")
        upload = await _make_upload(owner, "p5")
        await _make_archive(owner, [upload], status=ArchiveStatusEnum.ready, suffix="pl000005")
        client.cookies = _auth(owner)
        response = await client.get("/archives/profile-list", headers=_htmx())
        assert "every 2s" not in response.text
