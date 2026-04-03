"""Tests for the single file view page endpoints.

- GET /view/{id} — SEO redirect to canonical URL with filename
- GET /view/{id}/{filename} — render upload view page
- View page content: file preview, metadata panel, sharing options, and edit form visibility
"""

import pytest
from pathlib import Path

from app.models.users import User
from app.models.uploads import Upload
from app.lib.auth import create_access_token


# ---------------------------------------------------------------------------
# View page helpers
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def mock_upload_file_exists_for_view_tests(request, monkeypatch):
    """Mock upload.filepath.exists() for view tests so they pass validate_file_request."""
    if "TestViewUploadPage" in request.node.parent.name:
        original_exists = Path.exists

        def mock_exists(self: Path) -> bool:
            if "viewfile" in self.name:
                return True
            return original_exists(self)

        monkeypatch.setattr(Path, "exists", mock_exists)


def _view_upload_data(user, suffix: str = "") -> dict:
    """Minimal Upload.create kwargs for view page tests."""
    return {
        "user": user,
        "description": f"view test {suffix}",
        "name": f"viewfile{suffix}_20250309-000000_a1b2c3d4",
        "cleanname": f"viewfile{suffix}",
        "originalname": f"viewfile{suffix}.txt",
        "ext": "txt",
        "size": 1024,
        "type": "text/plain",
        "extra": "0",
        "private": 0,
    }


# ---------------------------------------------------------------------------
# Step 1: View route tests
# ---------------------------------------------------------------------------

class TestViewUploadPageRedirectEndpoint:
    """Tests for GET /view/{id} (SEO redirect without filename)."""

    async def test_public_upload_redirects_to_view_with_filename(self, client):
        """Public upload redirects to the canonical view URL with filename."""
        user = await User.create(username="viewredir1", email="viewredir1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "redir1"))

        response = await client.get(f"/view/{upload.id}", follow_redirects=False)

        assert response.status_code == 301
        location = response.headers["location"]
        assert f"/view/{upload.id}/" in location
        assert upload.cleanname in location

    async def test_nonexistent_upload_returns_404(self, client):
        """Non-existent upload ID returns 404."""
        response = await client.get("/view/999999", follow_redirects=False)
        assert response.status_code == 404

    async def test_private_upload_returns_403(self, client):
        """Private upload without user context returns 403 (prevents info disclosure)."""
        user = await User.create(username="viewredir3", email="viewredir3@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "redir3"), "private": 1})

        client.cookies.clear()
        response = await client.get(f"/view/{upload.id}", follow_redirects=False)

        assert response.status_code == 403


class TestViewUploadPageEndpoint:
    """Tests for GET /view/{id}/{filename} view page — Step 1."""

    async def test_public_upload_accessible_to_anonymous_users(self, client):
        """Anonymous users can view public uploads."""
        user = await User.create(username="viewanon1", email="viewanon1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "anon1"))

        client.cookies.clear()
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200

    async def test_public_upload_accessible_to_authenticated_users(self, client):
        """Authenticated users can view public uploads."""
        user = await User.create(username="viewauth1", email="viewauth1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "auth1"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200

    async def test_private_upload_accessible_to_owner(self, client):
        """Owners can view their own private uploads."""
        user = await User.create(username="viewowner1", email="viewowner1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "owner1"), "private": 1})

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200

    async def test_private_upload_returns_403_for_other_users(self, client):
        """Non-owners receive 403 when attempting to view a private upload."""
        owner = await User.create(username="viewprivown", email="viewprivown@example.com", password="pw", is_registered=True)
        other = await User.create(username="viewprivoth", email="viewprivoth@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(owner, "priv403"), "private": 1})

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 403

    async def test_private_upload_returns_403_for_anonymous_users(self, client):
        """Anonymous users receive 403 when attempting to view a private upload."""
        user = await User.create(username="viewprivanon", email="viewprivanon@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "privanon"), "private": 1})

        client.cookies.clear()
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 403

    async def test_nonexistent_upload_returns_404(self, client):
        """Non-existent upload ID returns 404."""
        response = await client.get("/view/999999/nonexistent.txt")
        assert response.status_code == 404

    async def test_page_returns_html(self, client):
        """View page returns HTML content."""
        user = await User.create(username="viewhtml1", email="viewhtml1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "html1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_page_renders_original_filename(self, client):
        """View page renders the upload's original filename."""
        user = await User.create(username="viewfname1", email="viewfname1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "fname1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert upload.originalname in response.text


# ---------------------------------------------------------------------------
# Steps 2, 3, 4: View page content tests
# ---------------------------------------------------------------------------

class TestViewUploadPageContent:
    """Tests for file preview, metadata, and sharing content — Steps 2, 3, 4."""

    # Step 2: File preview

    async def test_image_upload_shows_image_frame(self, client):
        """Image uploads render the HTMX-triggered view-frame-image element."""
        from app.models.images import Image
        user = await User.create(username="viewimg1", email="viewimg1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "img1"), "type": "image/jpeg", "ext": "jpg", "originalname": "viewfileimg1.jpg"})
        await Image.create(upload=upload, type="jpg", width=800, height=600, bits=8, channels=3)

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.jpg")

        assert response.status_code == 200
        assert "view-frame-image" in response.text

    async def test_non_image_upload_shows_file_extension(self, client):
        """Non-image uploads display the file extension in the file icon area."""
        user = await User.create(username="viewext1", email="viewext1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "ext1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200
        assert ".txt" in response.text

    async def test_non_image_upload_does_not_show_image_frame(self, client):
        """Non-image uploads do not render the image view frame element."""
        user = await User.create(username="viewnoimg1", email="viewnoimg1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "noimg1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "view-frame-image" not in response.text

    # Step 3: Metadata

    async def test_metadata_shows_uploader_username(self, client):
        """Metadata panel shows the uploader's username."""
        user = await User.create(username="viewmeta1", email="viewmeta1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "meta1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "viewmeta1" in response.text

    async def test_metadata_shows_mime_type(self, client):
        """Metadata panel shows the upload's MIME type."""
        user = await User.create(username="viewmeta2", email="viewmeta2@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "meta2"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "text/plain" in response.text

    async def test_metadata_shows_view_count_icon(self, client):
        """Metadata panel includes the view count field."""
        user = await User.create(username="viewmeta3", email="viewmeta3@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "meta3"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "icon-view-count" in response.text

    async def test_metadata_shows_upload_date_icon(self, client):
        """Metadata panel includes the upload date field."""
        user = await User.create(username="viewmeta4", email="viewmeta4@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "meta4"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "icon-calendar" in response.text

    async def test_image_metadata_shows_dimensions(self, client):
        """Image uploads show width × height in the metadata panel."""
        from app.models.images import Image
        user = await User.create(username="viewdims1", email="viewdims1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "dims1"), "type": "image/jpeg", "ext": "jpg", "originalname": "viewfiledims1.jpg"})
        await Image.create(upload=upload, type="jpg", width=1920, height=1080, bits=8, channels=3)

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.jpg")

        assert "1920" in response.text
        assert "1080" in response.text

    async def test_non_image_metadata_does_not_show_dimensions(self, client):
        """Non-image uploads do not include the image dimensions field."""
        user = await User.create(username="viewdims2", email="viewdims2@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "dims2"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "#icon-image-dimensions" not in response.text

    # Step 4: Sharing options

    async def test_share_button_shown_for_public_upload(self, client):
        """Share button is rendered for public uploads."""
        user = await User.create(username="viewshare1", email="viewshare1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "share1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200
        assert "Share upload" in response.text

    async def test_share_button_not_shown_for_private_upload(self, client):
        """Share button is not rendered for private uploads."""
        owner = await User.create(username="viewshare2", email="viewshare2@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(owner, "share2"), "private": 1})

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200
        assert "Share upload" not in response.text



    # Step 5 (partial): edit form owner/non-owner visibility

    async def test_edit_form_visible_to_owner(self, client):
        """Owner sees the Alpine.js inline-edit description component."""
        owner = await User.create(username="viewedit1", email="viewedit1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(owner, "edit1"))

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert 'id="upload-description"' in response.text

    async def test_edit_form_not_visible_to_non_owners(self, client):
        """Non-owners see only the read-only description paragraph, not the edit component."""
        owner = await User.create(username="viewedit2own", email="viewedit2own@example.com", password="pw", is_registered=True)
        other = await User.create(username="viewedit2oth", email="viewedit2oth@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(owner, "edit2"))

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert 'id="upload-description"' not in response.text

    async def test_edit_form_not_visible_to_anonymous_users(self, client):
        """Anonymous users see only the read-only description paragraph."""
        user = await User.create(username="viewedit3", email="viewedit3@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "edit3"))

        client.cookies.clear()
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert 'id="upload-description"' not in response.text
