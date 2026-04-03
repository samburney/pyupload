"""Tests for app/api/images.py - Image manipulation API endpoints.

Covers:
- POST /api/v1/images/{id}/rotate
  - 400 invalid angle
  - 401 unauthenticated
  - 404 upload not found
  - 403 private upload, non-owner
  - 200 success - response structure and correct behaviour
"""

from unittest.mock import AsyncMock, patch

from app.models.users import User
from app.models.uploads import Upload
from app.models.images import Image
from app.lib.auth import create_access_token


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


class TestPostRotateImage:
    """Test POST /api/v1/images/{id}/rotate."""

    async def test_invalid_angle_returns_400(self, client):
        """Angles outside [90, 180, 270] must be rejected before any DB access."""
        user = await User.create(username="rotbadangle", email="rotbadangle@example.com", password="pw")
        token = create_access_token({"sub": user.username})

        response = await client.post(
            "/api/v1/images/999/rotate",
            params={"angle": 45},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 400
        assert "angle" in response.json()["detail"].lower()

    async def test_unauthenticated_returns_401(self, client):
        """Requests without a valid Bearer token must be rejected."""
        response = await client.post("/api/v1/images/1/rotate", params={"angle": 90})
        assert response.status_code == 401

    async def test_upload_not_found_returns_404(self, client):
        """A valid angle for a non-existent upload must return 404."""
        user = await User.create(username="rotnotfound", email="rotnotfound@example.com", password="pw")
        token = create_access_token({"sub": user.username})

        response = await client.post(
            "/api/v1/images/99999/rotate",
            params={"angle": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 404

    async def test_private_upload_non_owner_returns_403(self, client):
        """A private upload must not be rotatable by a different user."""
        owner = await User.create(username="rotowner", email="rotowner@example.com", password="pw")
        other = await User.create(username="rotother", email="rotother@example.com", password="pw")
        upload = await _create_image_upload(owner, private=1)

        token = create_access_token({"sub": other.username})

        response = await client.post(
            f"/api/v1/images/{upload.id}/rotate",
            params={"angle": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    async def test_public_upload_non_owner_returns_403(self, client):
        """A public upload must not be rotatable by a different user."""
        owner = await User.create(username="rotpubowner", email="rotpubowner@example.com", password="pw")
        other = await User.create(username="rotpubother", email="rotpubother@example.com", password="pw")
        upload = await _create_image_upload(owner, private=0)

        token = create_access_token({"sub": other.username})

        response = await client.post(
            f"/api/v1/images/{upload.id}/rotate",
            params={"angle": 90},
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 403

    async def test_success_returns_200_with_upload_data(self, client):
        """A valid rotation request must return 200 with serialised upload data."""
        user = await User.create(username="rotsuccess", email="rotsuccess@example.com", password="pw")
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})

        with patch("app.api.images.validate_file_update_request", return_value=True):
            with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
                response = await client.post(
                    f"/api/v1/images/{upload.id}/rotate",
                    params={"angle": 90},
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == upload.id
        assert data["type"] == "image/jpeg"

    async def test_success_calls_rotate_image_with_correct_angle(self, client):
        """rotate_image must be called with exactly the angle supplied in the request."""
        user = await User.create(username="rotangle", email="rotangle@example.com", password="pw")
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})

        mock_rotate = AsyncMock(return_value=True)
        with patch("app.api.images.validate_file_update_request", return_value=True):
            with patch.object(Upload, "rotate_image", new=mock_rotate):
                await client.post(
                    f"/api/v1/images/{upload.id}/rotate",
                    params={"angle": 270},
                    headers={"Authorization": f"Bearer {token}"},
                )

        mock_rotate.assert_awaited_once_with(270)

    async def test_success_response_includes_image_metadata(self, client):
        """Response must include an 'image' key with basic image metadata."""
        user = await User.create(username="rotimgmeta", email="rotimgmeta@example.com", password="pw")
        upload = await _create_image_upload(user)
        token = create_access_token({"sub": user.username})

        with patch("app.api.images.validate_file_update_request", return_value=True):
            with patch.object(Upload, "rotate_image", new=AsyncMock(return_value=True)):
                response = await client.post(
                    f"/api/v1/images/{upload.id}/rotate",
                    params={"angle": 180},
                    headers={"Authorization": f"Bearer {token}"},
                )

        assert response.status_code == 200
        data = response.json()
        assert "image" in data
        assert data["image"]["width"] == 100
        assert data["image"]["height"] == 60
