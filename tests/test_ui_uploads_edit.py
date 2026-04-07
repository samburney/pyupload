"""Tests for upload mutation/edit endpoints.

- POST /uploads/delete — delete selected uploads (owner only, HTMX)
- PATCH /uploads/private — toggle upload privacy for a selection (owner only, HTMX)
- PATCH /uploads/{id}/description — update upload description (owner only, HTMX)
- Description max-length validation (255 characters)
"""

import pytest
from unittest.mock import patch

from app.models.users import User
from app.models.uploads import Upload
from app.lib.auth import create_access_token


# ---------------------------------------------------------------------------
# Upload helper (used by privacy toggle and description tests below)
# ---------------------------------------------------------------------------

def _tag_upload_data(user, suffix: str = "") -> dict:
    """Minimal Upload.create kwargs for upload-backed endpoint tests."""
    return {
        "user": user,
        "description": f"tag test {suffix}",
        "name": f"tagfile{suffix}_20250301-000000_a1b2c3d4",
        "cleanname": f"tagfile{suffix}",
        "originalname": f"tagfile{suffix}.txt",
        "ext": "txt",
        "size": 10,
        "type": "text/plain",
        "extra": "0",
    }


async def _create_tag_upload_with_file(user, suffix: str, tmp_path, monkeypatch) -> Upload:
    """Create a test upload with a real backing file in tmp storage."""
    import app.models.uploads

    monkeypatch.setattr(app.models.uploads.config, "storage_path", tmp_path)
    upload = await Upload.create(**_tag_upload_data(user, suffix))
    upload.filepath.parent.mkdir(parents=True, exist_ok=True)
    upload.filepath.write_text("tag test file")

    return upload


def _htmx_upload_delete() -> dict:
    return {"HX-Request": "true", "HX-Target": "upload-sidebar"}


def _htmx_gallery_delete() -> dict:
    return {"HX-Request": "true", "HX-Target": "gallery-grid"}


class TestDeleteSelectedUploadsPost:
    """Tests for POST /uploads/delete."""

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests must redirect to /login."""
        response = await client.post(
            "/uploads/delete",
            data={"redirect": "http://testserver/profile", "selected_ids": [1]},
            headers=_htmx_upload_delete(),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_returns_400_without_htmx_header(self, client):
        """Non-HTMX requests are rejected with 400."""
        user = await User.create(
            username="udel400",
            email="udel400@example.com",
            password="pw",
            is_registered=True,
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post(
            "/uploads/delete",
            data={"redirect": "http://testserver/profile", "selected_ids": [1]},
        )
        assert response.status_code == 400

    async def test_returns_403_for_non_owner(self, client):
        """Returns 403 when no selected uploads are writable by the current user."""
        owner = await User.create(
            username="udelowner",
            email="udelowner@example.com",
            password="pw",
            is_registered=True,
        )
        other = await User.create(
            username="udelother",
            email="udelother@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await Upload.create(
            user=owner,
            description="",
            name="udeltest_20250101-000000_a1b2c3d4",
            cleanname="udeltest",
            originalname="udeltest.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="0",
        )
        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post(
            "/uploads/delete",
            data={"redirect": "http://testserver/profile", "selected_ids": [upload.id]},
            headers=_htmx_upload_delete(),
        )
        assert response.status_code == 403

    async def test_view_page_returns_204_with_hx_redirect(self, client):
        """View page context (HX-Target: upload-sidebar) returns HX-Redirect."""
        user = await User.create(
            username="udelsucc",
            email="udelsucc@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await Upload.create(
            user=user,
            description="",
            name="udelsuccfile_20250101-000000_a1b2c3d4",
            cleanname="udelsuccfile",
            originalname="udelsuccfile.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="0",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch("app.lib.file_io.delete_file"):
            response = await client.post(
                "/uploads/delete",
                data={"redirect": "http://testserver/profile", "selected_ids": [upload.id]},
                headers=_htmx_upload_delete(),
                follow_redirects=False,
            )

        assert response.status_code == 204
        assert response.headers.get("HX-Redirect") == "http://testserver/profile"
        assert "HX-Location" not in response.headers

    async def test_gallery_context_returns_204_with_hx_location(self, client):
        """Gallery context (HX-Target: gallery-grid) returns HX-Location with gallery target."""
        user = await User.create(
            username="udelgal",
            email="udelgal@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await Upload.create(
            user=user,
            description="",
            name="udelgalfile_20250101-000000_a1b2c3d4",
            cleanname="udelgalfile",
            originalname="udelgalfile.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="0",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch("app.lib.file_io.delete_file"):
            response = await client.post(
                "/uploads/delete",
                data={"redirect": "http://testserver/", "selected_ids": [upload.id]},
                headers=_htmx_gallery_delete(),
                follow_redirects=False,
            )

        assert response.status_code == 204
        assert "HX-Location" in response.headers
        assert "HX-Trigger" in response.headers
        assert "HX-Redirect" not in response.headers

    async def test_removes_upload_from_database_on_success(self, client):
        """Successful delete removes the upload record from the database."""
        user = await User.create(
            username="udeldb",
            email="udeldb@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await Upload.create(
            user=user,
            description="",
            name="udeldbfile_20250101-000000_b2c3d4e5",
            cleanname="udeldbfile",
            originalname="udeldbfile.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="0",
        )
        upload_id = upload.id
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch("app.lib.file_io.delete_file"):
            await client.post(
                "/uploads/delete",
                data={"redirect": "http://testserver/profile", "selected_ids": [upload_id]},
                headers=_htmx_upload_delete(),
            )

        assert await Upload.get_or_none(id=upload_id) is None


class TestUploadPrivateTogglePatchEndpoint:
    """Tests for PATCH /uploads/private."""

    def _htmx_upload_sidebar(self) -> dict:
        return {"HX-Request": "true", "HX-Target": "upload-sidebar"}

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.patch(
            "/uploads/private",
            data={"selected_ids": [1]},
            headers=self._htmx_upload_sidebar(),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when none of the selected uploads exist or are writable."""
        user = await User.create(
            username="priv404",
            email="priv404@example.com",
            password="pw",
            is_registered=True,
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch(
            "/uploads/private",
            data={"selected_ids": [999999], "upload_private": "true"},
            headers=self._htmx_upload_sidebar(),
        )
        assert response.status_code == 404

    async def test_owner_can_toggle_public_to_private(self, client, tmp_path, monkeypatch):
        """Owner can set a public upload to private and receives updated toggle HTML."""
        owner = await User.create(
            username="privown1",
            email="privown1@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await _create_tag_upload_with_file(owner, "privtoggle1", tmp_path, monkeypatch)

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        response = await client.patch(
            "/uploads/private",
            data={"selected_ids": [upload.id], "upload_private": "true"},
            headers=self._htmx_upload_sidebar(),
        )
        assert response.status_code == 200
        assert "Private" in response.text
        assert "checked" in response.text
        assert 'hx-patch="/uploads/private"' in response.text

        await upload.refresh_from_db()
        assert upload.private == 1

    async def test_owner_can_toggle_private_to_public(self, client, tmp_path, monkeypatch):
        """Owner can clear private status and receives updated toggle HTML."""
        owner = await User.create(
            username="privown2",
            email="privown2@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await _create_tag_upload_with_file(owner, "privtoggle2", tmp_path, monkeypatch)
        upload.private = 1
        await upload.save()

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        response = await client.patch(
            "/uploads/private",
            data={"selected_ids": [upload.id]},
            headers=self._htmx_upload_sidebar(),
        )
        assert response.status_code == 200
        assert "Public" in response.text
        assert 'class="peer sr-only" checked' not in response.text

        await upload.refresh_from_db()
        assert upload.private == 0

    async def test_non_owner_cannot_toggle_privacy(self, client, tmp_path, monkeypatch):
        """Non-owners receive 404 (upload excluded from writable set) and privacy is unchanged."""
        owner = await User.create(
            username="privowner",
            email="privowner@example.com",
            password="pw",
            is_registered=True,
        )
        other = await User.create(
            username="privother",
            email="privother@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await _create_tag_upload_with_file(owner, "privtoggle3", tmp_path, monkeypatch)

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.patch(
            "/uploads/private",
            data={"selected_ids": [upload.id], "upload_private": "true"},
            headers=self._htmx_upload_sidebar(),
        )
        assert response.status_code == 404

        await upload.refresh_from_db()
        assert upload.private == 0


class TestUploadDescriptionPatchEndpoint:
    """Tests for PATCH /uploads/{id}/description."""

    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.patch("/uploads/1/description", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when the upload does not exist."""
        user = await User.create(
            username="desc404",
            email="desc404@example.com",
            password="pw",
            is_registered=True,
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/uploads/999999/description", data={"description": "hello"})
        assert response.status_code == 404
        assert "Upload not found" in response.text

    async def test_owner_can_update_description(self, client, tmp_path, monkeypatch):
        """Owner can set a description and receives updated description HTML."""
        owner = await User.create(
            username="descown1",
            email="descown1@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await _create_tag_upload_with_file(owner, "desctoggle1", tmp_path, monkeypatch)

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        response = await client.patch(f"/uploads/{upload.id}/description", data={"description": "My new description"})
        assert response.status_code == 200

        await upload.refresh_from_db()
        assert upload.description == "My new description"

    async def test_owner_can_clear_description(self, client, tmp_path, monkeypatch):
        """Owner can clear the description by submitting an empty string."""
        owner = await User.create(
            username="descown2",
            email="descown2@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await _create_tag_upload_with_file(owner, "desctoggle2", tmp_path, monkeypatch)
        upload.description = "Some existing description"
        await upload.save()

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        response = await client.patch(f"/uploads/{upload.id}/description")
        assert response.status_code == 200

        await upload.refresh_from_db()
        assert upload.description == ""

    async def test_description_is_html_escaped(self, client, tmp_path, monkeypatch):
        """HTML characters in description are escaped to prevent XSS."""
        owner = await User.create(
            username="descesc",
            email="descesc@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await _create_tag_upload_with_file(owner, "descescape", tmp_path, monkeypatch)

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        await client.patch(f"/uploads/{upload.id}/description", data={"description": "<script>alert('xss')</script>"})

        await upload.refresh_from_db()
        assert "<script>" not in upload.description
        assert "&lt;script&gt;" in upload.description

    async def test_non_owner_cannot_update_description(self, client, tmp_path, monkeypatch):
        """Non-owners receive 403 and the upload description is unchanged."""
        owner = await User.create(
            username="descowner",
            email="descowner@example.com",
            password="pw",
            is_registered=True,
        )
        other = await User.create(
            username="descother",
            email="descother@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await _create_tag_upload_with_file(owner, "desctoggle3", tmp_path, monkeypatch)
        original_description = upload.description

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.patch(f"/uploads/{upload.id}/description", data={"description": "Hijacked!"})
        assert response.status_code == 403

        await upload.refresh_from_db()
        assert upload.description == original_description


class TestDescriptionMaxLengthValidation:
    """Step 5 test 5: max-length validation for the description field (255 chars)."""

    async def test_description_at_max_length_is_accepted(self, client, tmp_path, monkeypatch):
        """A 255-character description is accepted and persisted."""
        owner = await User.create(username="descmaxok", email="descmaxok@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(owner, "maxok", tmp_path, monkeypatch)

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        description = "a" * 255
        response = await client.patch(f"/uploads/{upload.id}/description", data={"description": description})

        assert response.status_code == 200
        await upload.refresh_from_db()
        assert upload.description == description

    async def test_description_over_max_length_returns_400(self, client, tmp_path, monkeypatch):
        """A description exceeding 255 characters returns 400 with a validation error."""
        owner = await User.create(username="descmaxfail", email="descmaxfail@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(owner, "maxfail", tmp_path, monkeypatch)

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        description = "a" * 256
        response = await client.patch(f"/uploads/{upload.id}/description", data={"description": description})

        assert response.status_code == 400
