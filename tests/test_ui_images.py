"""Tests for app/ui/images.py - Image UI endpoints.

Covers:
- POST /images/{id}/rotate/{angle}
  - 400 invalid angle (rendered HTML error page, not empty response)
  - 404 upload not found (rendered HTML error page)
  - 403 unauthenticated (no auth cookie)
  - 403 non-owner
  - 200 success (HTML view page)
  - flash message present in successful rotation response
  - rotate_image called with the correct angle
  - all valid angles accepted (90, 180, 270)
"""

import pytest
from unittest.mock import AsyncMock, patch

from app.lib.auth import create_access_token
from app.models.images import Image
from app.models.uploads import Upload
from app.models.users import User


async def _create_image_upload(user: User, private: int = 0) -> Upload:
    """Create an Upload with a linked Image record."""
    upload = await Upload.create(
        user=user,
        description="Test image",
        name="testimg_20250101-000000_a1b2c3d4",
        cleanname="testimg",
        originalname="testimg.jpg",
        ext="jpg",
        size=1000,
        type="image/jpeg",
        extra="0",
        private=private,
    )
    await Image.create(upload=upload, type="jpeg", width=100, height=60, bits=24, channels=3)
    return upload


_PATCHED_VALIDATE_UPDATE = "app.ui.images.validate_file_update_request"
_PATCHED_VALIDATE_VIEW = "app.ui.uploads.validate_file_request"


class TestPostRotateImageUI:
    """Tests for POST /images/{id}/rotate/{angle} UI endpoint."""

    # ------------------------------------------------------------------
    # Invalid angle
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_invalid_angle_returns_400(self, client):
        """An angle outside [90, 180, 270] must return HTTP 400."""
        user = await User.create(
            username="uirotinv400",
            email="uirotinv400@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.post("/images/999/rotate/45")
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_invalid_angle_returns_rendered_html_not_empty(self, client):
        """The 400 response must be a rendered error page, not an empty body.

        This specifically validates the bug fix ensuring request=request is
        passed to error_response_for_get so the Jinja2 template is rendered.
        """
        user = await User.create(
            username="uirotinvhtml",
            email="uirotinvhtml@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.post("/images/999/rotate/45")
        assert response.status_code == 400
        assert "text/html" in response.headers.get("content-type", "")
        # A rendered template will always be substantially longer than an empty HTMLResponse
        assert len(response.text) > 100

    @pytest.mark.asyncio
    async def test_invalid_angle_response_contains_error_title(self, client):
        """The rendered 400 error page must include the error title."""
        user = await User.create(
            username="uirotinvtitle",
            email="uirotinvtitle@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.post("/images/999/rotate/45")
        assert "Invalid Rotation Angle" in response.text

    @pytest.mark.asyncio
    @pytest.mark.parametrize("angle", [0, 45, 91, 180000, -90, 360])
    async def test_various_invalid_angles_return_400(self, client, angle):
        """All angles outside [90, 180, 270] must be rejected with 400."""
        user = await User.create(
            username=f"uirotinv{abs(angle)}",
            email=f"uirotinv{abs(angle)}@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.post(f"/images/999/rotate/{angle}")
        assert response.status_code == 400

    # ------------------------------------------------------------------
    # Upload not found
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_upload_not_found_returns_404(self, client):
        """A valid angle for a non-existent upload must return HTTP 404."""
        user = await User.create(
            username="uirotnotfound",
            email="uirotnotfound@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/images/99999/rotate/90")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_upload_not_found_returns_rendered_html(self, client):
        """The 404 response must be a rendered HTML error page."""
        user = await User.create(
            username="uirotnotfound2",
            email="uirotnotfound2@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/images/99999/rotate/90")
        assert response.status_code == 404
        assert "text/html" in response.headers.get("content-type", "")
        assert len(response.text) > 100

    # ------------------------------------------------------------------
    # Authorisation
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_unauthenticated_redirects_to_login(self, client):
        """A request without an auth cookie must redirect to the login page (303)."""
        user = await User.create(
            username="uirotunauthowner",
            email="uirotunauthowner@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)

        # No auth cookie set — LoginRequiredException → redirect to /login
        response = await client.post(f"/images/{upload.id}/rotate/90")
        assert response.status_code == 303

    @pytest.mark.asyncio
    async def test_non_owner_returns_403(self, client):
        """A request from a user who does not own the upload must return 403."""
        owner = await User.create(
            username="uirotowner",
            email="uirotowner@example.com",
            password="pw",
        )
        other = await User.create(
            username="uirotother",
            email="uirotother@example.com",
            password="pw",
        )
        upload = await _create_image_upload(owner)

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/images/{upload.id}/rotate/90")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_private_upload_non_owner_returns_403(self, client):
        """A private upload must not be rotatable by a different user."""
        owner = await User.create(
            username="uirotprivowner",
            email="uirotprivowner@example.com",
            password="pw",
        )
        other = await User.create(
            username="uirotprivother",
            email="uirotprivother@example.com",
            password="pw",
        )
        upload = await _create_image_upload(owner, private=1)

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/images/{upload.id}/rotate/90")
        assert response.status_code == 403

    # ------------------------------------------------------------------
    # Success
    # ------------------------------------------------------------------

    @pytest.mark.asyncio
    async def test_success_returns_200_html(self, client):
        """A valid rotation request from the owner must return 200 HTML."""
        user = await User.create(
            username="uirotsuccess",
            email="uirotsuccess@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch(_PATCHED_VALIDATE_UPDATE, return_value=True):
            with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
                with patch(_PATCHED_VALIDATE_VIEW, return_value=True):
                    response = await client.post(f"/images/{upload.id}/rotate/90")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_success_calls_rotate_image_with_correct_angle(self, client):
        """rotate_image must be called with exactly the angle from the URL."""
        user = await User.create(
            username="uirotangle",
            email="uirotangle@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        mock_rotate = AsyncMock(return_value=True)
        with patch(_PATCHED_VALIDATE_UPDATE, return_value=True):
            with patch.object(Upload, "rotate_image", new=mock_rotate):
                with patch(_PATCHED_VALIDATE_VIEW, return_value=True):
                    await client.post(f"/images/{upload.id}/rotate/270")

        mock_rotate.assert_awaited_once_with(270)

    @pytest.mark.asyncio
    @pytest.mark.parametrize("angle", [90, 180, 270])
    async def test_all_valid_angles_return_200(self, client, angle):
        """All valid rotation angles (90, 180, 270) must be accepted."""
        user = await User.create(
            username=f"uirotvalid{angle}",
            email=f"uirotvalid{angle}@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch(_PATCHED_VALIDATE_UPDATE, return_value=True):
            with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
                with patch(_PATCHED_VALIDATE_VIEW, return_value=True):
                    response = await client.post(f"/images/{upload.id}/rotate/{angle}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_success_response_contains_flash_message(self, client):
        """A successful rotation must produce a flash message in the response."""
        user = await User.create(
            username="uirotflash",
            email="uirotflash@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch(_PATCHED_VALIDATE_UPDATE, return_value=True):
            with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
                with patch(_PATCHED_VALIDATE_VIEW, return_value=True):
                    response = await client.post(f"/images/{upload.id}/rotate/90")

        assert response.status_code == 200
        assert "rotated" in response.text.lower() or "success" in response.text.lower() or "90" in response.text
