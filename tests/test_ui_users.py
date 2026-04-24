"""Tests for app/ui/users.py — User profile and uploads gallery pages.

Covers:
- GET /profile: authentication required, default and explicit sort order,
  upload and image rendering, pagination, download archives section
- GET /uploads: authentication required, shows only current user's uploads
  (including private), excludes other users' uploads
"""

from datetime import datetime, timedelta, timezone

from app.lib.auth import create_access_token
from app.lib.config import get_app_config
from app.models.images import Image
from app.models.users import User
from app.models.uploads import Upload
from app.models.download_archives import DownloadArchive, ArchiveFormatsEnum, ArchiveStatusEnum


config = get_app_config()


def _upload_kwargs(user: User, suffix: str, *, size: int = 100) -> dict:
    """Minimal Upload.create kwargs."""
    return {
        "user": user,
        "description": f"file {suffix}",
        "name": f"proffile{suffix}_20250101-000000_a1b2c3d4",
        "cleanname": f"proffile{suffix}",
        "originalname": f"proffile{suffix}.txt",
        "ext": "txt",
        "size": size,
        "type": "text/plain",
        "extra": "",
    }


async def _make_archive_for_user(user: User, status: ArchiveStatusEnum, suffix: str) -> DownloadArchive:
    return await DownloadArchive.create(
        user=user,
        upload_ids=[],
        format=ArchiveFormatsEnum.zip,
        status=status,
        filename=f"archive_{user.username}_20260101-000000_{suffix}.zip",
    )


# ---------------------------------------------------------------------------
# GET /profile — sorting
# ---------------------------------------------------------------------------

class TestUserProfileSorting:
    """Verify sort_by / sort_order parameters are honoured."""

    async def test_default_sort_returns_newest_upload_first(self, client):
        """With no explicit sort params the page uses created_at desc — newest first."""
        user = await User.create(username="profdeflt", email="profdeflt@example.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        older = await Upload.create(**_upload_kwargs(user, "old"))
        newer = await Upload.create(**_upload_kwargs(user, "new"))

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        # Newer upload should appear before the older one in the rendered output
        assert html.index("proffilenew.txt") < html.index("proffileold.txt")

    async def test_explicit_sort_by_size_asc_orders_smallest_first(self, client):
        """sort_by=size&sort_order=asc renders the smallest upload first."""
        user = await User.create(username="profsort", email="profsort@example.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        await Upload.create(**_upload_kwargs(user, "big", size=9000))
        await Upload.create(**_upload_kwargs(user, "sml", size=1))

        response = await client.get("/profile?sort_by=size&sort_order=asc")

        assert response.status_code == 200
        html = response.text
        # Smallest upload (sml) should appear before the larger one (big)
        assert html.index("proffilesml.txt") < html.index("proffilebig.txt")


# ---------------------------------------------------------------------------
# GET /profile — rendering
# ---------------------------------------------------------------------------

class TestUserProfileRendering:
    """Integration tests for profile page content rendering."""

    async def test_empty_profile_shows_no_uploads_section(self, client):
        """Profile page with no uploads omits the uploads section."""
        user = await User.create(username="profempty", email="profempty@example.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        assert "Profile" in html
        assert user.username in html
        assert "<strong>Uploads</strong>" not in html

    async def test_profile_renders_text_upload(self, client):
        """A plain-text upload is rendered with filename and extension badge."""
        user = await User.create(username="proftxt", email="proftxt@example.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        upload = await Upload.create(
            user=user, description="text", name="notes_20250101-000000_a1b2c3d4",
            cleanname="notes", originalname="notes.txt", ext="txt",
            size=1024, type="text/plain", extra="",
        )

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        assert "notes.txt" in html
        assert upload.url in html

    async def test_profile_renders_image_upload_with_img_tag(self, client):
        """An image upload is rendered with an <img> tag pointing to the upload URL."""
        user = await User.create(username="profimg", email="profimg@example.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        upload = await Upload.create(
            user=user, description="photo", name="photo_20250101-000000_a1b2c3d4",
            cleanname="photo", originalname="photo.jpg", ext="jpg",
            size=2048, type="image/jpeg", extra="",
        )
        await Image.create(upload=upload, type="jpeg", width=100, height=100, bits=8, channels=3)

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        assert "photo.jpg" in html
        assert "<img" in html
        assert f'src="{upload.url}?t=' in html

    async def test_profile_pagination_respects_page_size(self, client):
        """Profile page shows at most the default page size worth of uploads."""
        user = await User.create(username="profpaged", email="profpaged@example.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        for i in range(15):
            await Upload.create(**{**_upload_kwargs(user, str(i)), "originalname": f"pgfile{i}.txt"})

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        # Default page size is 10; the count of "Filename:" labels should not exceed that
        assert html.count("Filename:") <= 10


# ---------------------------------------------------------------------------
# GET /profile — download archives section
# ---------------------------------------------------------------------------

class TestUserProfileArchives:
    """Tests for the Download Archives section on the profile page."""

    async def test_shows_archive_section_with_pending_entry(self, client):
        """A pending archive appears in the archives section."""
        user = await User.create(username="arch_pending", email="arch_pending@test.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        archive = await _make_archive_for_user(user, ArchiveStatusEnum.pending, "aa000001")

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        assert "Download Archives" in html
        assert archive.filename in html
        assert "Pending" in html

    async def test_shows_download_link_for_ready_archive(self, client):
        """A ready archive shows a download link."""
        user = await User.create(username="arch_ready", email="arch_ready@test.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        archive = await _make_archive_for_user(user, ArchiveStatusEnum.ready, "aa000002")

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        assert "Download Archives" in html
        assert archive.filename in html
        assert "/download/" in html

    async def test_omits_archive_section_when_no_archives(self, client):
        """Profile page omits the archives section entirely when none exist."""
        user = await User.create(username="arch_none", email="arch_none@test.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        assert "Download Archives" not in html
        assert "profile-download-archives-table" not in html

    async def test_does_not_show_expired_archives(self, client):
        """Expired archives are excluded from the profile page."""
        user = await User.create(username="arch_expired", email="arch_expired@test.com", is_registered=True, password="pw")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        archive = await _make_archive_for_user(user, ArchiveStatusEnum.ready, "aa000003")
        old_time = datetime.now(tz=timezone.utc) - timedelta(hours=config.archive_max_age_hours + 1)
        await DownloadArchive.filter(id=archive.id).update(created_at=old_time)

        response = await client.get("/profile")

        assert response.status_code == 200
        html = response.text
        assert "Download Archives" not in html
        assert archive.filename not in html


# ---------------------------------------------------------------------------
# GET /uploads — user gallery
# ---------------------------------------------------------------------------

class TestUserUploadsGallery:
    """Tests for the /uploads gallery page showing the current user's uploads."""

    async def test_uploads_requires_authentication(self, client):
        """GET /uploads redirects unauthenticated users."""
        response = await client.get("/uploads", follow_redirects=False)
        assert response.status_code in (302, 303, 401, 403)

    async def test_uploads_returns_200_for_authenticated_user(self, client):
        """GET /uploads returns 200 for an authenticated user."""
        user = await User.create(username="ugal-smoke", email="ugal-smoke@e.com", is_registered=True, password="pw")
        client.cookies = {"access_token": create_access_token({"sub": user.username})}

        response = await client.get("/uploads")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_uploads_shows_own_uploads(self, client):
        """GET /uploads shows the current user's own uploads."""
        user = await User.create(username="ugal-own", email="ugal-own@e.com", is_registered=True, password="pw")
        client.cookies = {"access_token": create_access_token({"sub": user.username})}
        upload = await Upload.create(**_upload_kwargs(user, "mine"))

        response = await client.get("/uploads")

        assert response.status_code == 200
        assert upload.originalname in response.text

    async def test_uploads_excludes_other_users_uploads(self, client):
        """GET /uploads does not show uploads belonging to other users."""
        user = await User.create(username="ugal-excl", email="ugal-excl@e.com", is_registered=True, password="pw")
        other = await User.create(username="ugal-excl-other", email="ugal-excl-other@e.com", is_registered=True, password="pw")
        client.cookies = {"access_token": create_access_token({"sub": user.username})}
        other_upload = await Upload.create(**_upload_kwargs(other, "notmine"))

        response = await client.get("/uploads")

        assert response.status_code == 200
        assert other_upload.originalname not in response.text

    async def test_uploads_includes_private_uploads(self, client):
        """GET /uploads shows the user's own private uploads."""
        user = await User.create(username="ugal-priv", email="ugal-priv@e.com", is_registered=True, password="pw")
        client.cookies = {"access_token": create_access_token({"sub": user.username})}
        private_upload = await Upload.create(**{**_upload_kwargs(user, "secret"), "private": True})

        response = await client.get("/uploads")

        assert response.status_code == 200
        assert private_upload.originalname in response.text
