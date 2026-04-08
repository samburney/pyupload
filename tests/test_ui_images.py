"""Tests for app/ui/images.py - Image UI endpoints.

Covers:
- POST /images/rotate (unified endpoint, replaces /{id}/rotate/{angle})
  - 303 unauthenticated (redirect to login)
  - 400 invalid angle (rendered HTML error page)
  - 404 no writable images in selection
  - view-frame context: 200 HTML view page with flash message
  - gallery context: 204 with HX-Location header
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


_PATCHED_VALIDATE_VIEW = "app.ui.uploads.validate_file_request"


def _htmx_view_rotate() -> dict:
    return {"HX-Request": "true", "HX-Target": "view-frame-image"}


def _htmx_gallery_rotate() -> dict:
    return {"HX-Request": "true", "HX-Target": "gallery-grid"}


class TestRotateSelectedImagesPost:
    """Tests for POST /images/rotate (unified endpoint)."""

    # ------------------------------------------------------------------
    # Authorisation
    # ------------------------------------------------------------------

    async def test_unauthenticated_redirects_to_login(self, client):
        """A request without an auth cookie must redirect to login (303)."""
        response = await client.post(
            "/images/rotate",
            data={"angle": 90, "selected_ids": [1]},
            headers=_htmx_view_rotate(),
            follow_redirects=False,
        )
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    # ------------------------------------------------------------------
    # Invalid angle
    # ------------------------------------------------------------------

    async def test_invalid_angle_returns_400(self, client):
        """An angle outside [90, 180, 270] must return HTTP 400."""
        user = await User.create(
            username="rotinv400",
            email="rotinv400@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.post(
            "/images/rotate",
            data={"angle": 45, "selected_ids": [1]},
            headers=_htmx_view_rotate(),
        )
        assert response.status_code == 400

    async def test_invalid_angle_returns_rendered_html(self, client):
        """The 400 response must be a rendered HTML error page."""
        user = await User.create(
            username="rotinvhtml",
            email="rotinvhtml@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.post(
            "/images/rotate",
            data={"angle": 45, "selected_ids": [1]},
            headers=_htmx_view_rotate(),
        )
        assert response.status_code == 400
        assert "text/html" in response.headers.get("content-type", "")
        assert "Invalid Rotation Angle" in response.text

    @pytest.mark.parametrize("angle", [0, 45, 91, 180000, 360])
    async def test_various_invalid_angles_return_400(self, client, angle):
        """All angles outside [90, 180, 270] must be rejected with 400."""
        user = await User.create(
            username=f"rotinv{abs(angle)}",
            email=f"rotinv{abs(angle)}@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.post(
            "/images/rotate",
            data={"angle": angle, "selected_ids": [1]},
            headers=_htmx_view_rotate(),
        )
        assert response.status_code == 400

    # ------------------------------------------------------------------
    # No writable images
    # ------------------------------------------------------------------

    async def test_no_images_in_selection_returns_404(self, client):
        """If no writable image uploads are in the selection, return 404."""
        user = await User.create(
            username="rotnoimages",
            email="rotnoimages@example.com",
            password="pw",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.post(
            "/images/rotate",
            data={"angle": 90, "selected_ids": [99999]},
            headers=_htmx_view_rotate(),
        )
        assert response.status_code == 404

    # ------------------------------------------------------------------
    # Success — view-frame context
    # ------------------------------------------------------------------

    async def test_view_context_returns_200_html(self, client):
        """View-frame context (HX-Target: view-frame-image) returns 200 HTML."""
        user = await User.create(
            username="rotviewok",
            email="rotviewok@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
            with patch(_PATCHED_VALIDATE_VIEW, return_value=True):
                response = await client.post(
                    "/images/rotate",
                    data={"angle": 90, "selected_ids": [upload.id]},
                    headers=_htmx_view_rotate(),
                )

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    async def test_view_context_contains_flash_message(self, client):
        """A successful view-frame rotation must include a flash message in the response."""
        user = await User.create(
            username="rotviewflash",
            email="rotviewflash@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
            with patch(_PATCHED_VALIDATE_VIEW, return_value=True):
                response = await client.post(
                    "/images/rotate",
                    data={"angle": 90, "selected_ids": [upload.id]},
                    headers=_htmx_view_rotate(),
                )

        assert "rotated" in response.text.lower()

    async def test_view_context_calls_rotate_image_with_correct_angle(self, client):
        """rotate_image must be called with exactly the submitted angle."""
        user = await User.create(
            username="rotviewangle",
            email="rotviewangle@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        mock_rotate = AsyncMock(return_value=True)
        with patch.object(Upload, "rotate_image", new=mock_rotate):
            with patch(_PATCHED_VALIDATE_VIEW, return_value=True):
                await client.post(
                    "/images/rotate",
                    data={"angle": 270, "selected_ids": [upload.id]},
                    headers=_htmx_view_rotate(),
                )

        mock_rotate.assert_awaited_once_with(270)

    @pytest.mark.parametrize("angle", [90, 180, 270])
    async def test_all_valid_angles_accepted_in_view_context(self, client, angle):
        """All valid rotation angles (90, 180, 270) must return 200 in view context."""
        user = await User.create(
            username=f"rotviewvalid{angle}",
            email=f"rotviewvalid{angle}@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
            with patch(_PATCHED_VALIDATE_VIEW, return_value=True):
                response = await client.post(
                    "/images/rotate",
                    data={"angle": angle, "selected_ids": [upload.id]},
                    headers=_htmx_view_rotate(),
                )

        assert response.status_code == 200

    # ------------------------------------------------------------------
    # Success — gallery context
    # ------------------------------------------------------------------

    async def test_gallery_context_returns_204_with_hx_location(self, client):
        """Gallery context (HX-Target: gallery-grid) returns 204 with HX-Location header."""
        user = await User.create(
            username="rotgalleryok",
            email="rotgalleryok@example.com",
            password="pw",
        )
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
            response = await client.post(
                "/images/rotate",
                data={"angle": 90, "selected_ids": [upload.id]},
                headers=_htmx_gallery_rotate(),
            )

        assert response.status_code == 204
        assert "HX-Location" in response.headers
