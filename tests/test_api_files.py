"""Tests for app/api/files.py - File metadata API endpoints.

This module tests the FastAPI file metadata endpoints:
- GET /api/v1/files/{id} - Get file metadata with URLs

Tests verify:
- File metadata retrieval
- Access control (private files owner-only)
- 404 for non-existent files
- 403 for unauthorized access
- Proper JSON response structure
- URL generation (get_url, view_url, download_url)
- Field transformations (name, originalname)
- Image metadata inclusion
- Authentication requirements
"""

import pytest
from app.models.users import User
from app.models.uploads import Upload
from app.models.images import Image
from app.lib.auth import create_access_token


class TestGetFileMetadata:
    """Test GET /api/v1/files/{id} endpoint."""

    @pytest.mark.asyncio
    async def test_get_file_metadata_success(self, client):
        """Test successful retrieval of file metadata."""
        # Create user and file
        user = await User.create(
            username="fileowner",
            email="owner@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        upload = await Upload.create(
            user=user,
            description="Test file",
            name="test_file",
            cleanname="test",
            originalname="test_file",
            ext="txt",
            size=1024,
            type="text/plain",
            extra="",
            private=0,
            viewed=5,
        )

        # Authenticate with Bearer token
        token = create_access_token({"sub": user.username})

        # Get file metadata
        response = await client.get(
            f"/api/v1/files/{upload.id}",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == upload.id
        assert data["description"] == "Test file"
        assert data["size"] == 1024
        assert data["type"] == "text/plain"
        assert data["viewed"] == 5

    @pytest.mark.asyncio
    async def test_get_file_metadata_returns_enriched_fields(self, client):
        """Test that response includes enriched fields."""
        user = await User.create(
            username="enricheduser",
            email="enriched@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        upload = await Upload.create(
            user=user,
            description="Enriched test",
            name="enriched_file",
            cleanname="enriched",
            originalname="enriched",
            ext="pdf",
            size=2048,
            type="application/pdf",
            extra="",
            private=1,
        )

        token = create_access_token({"sub": user.username})
        # Using Bearer token in headers

        response = await client.get(f"/api/v1/files/{upload.id}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        
        # Check enriched fields
        assert "is_image" in data
        assert "is_private" in data
        assert "is_owner" in data
        assert "get_url" in data
        assert "view_url" in data
        assert "download_url" in data
        
        assert data["is_private"] is True
        assert data["is_owner"] is True

    @pytest.mark.asyncio
    async def test_get_file_metadata_urls_are_absolute(self, client):
        """Test that URLs returned are absolute URLs."""
        user = await User.create(
            username="urluser",
            email="url@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        upload = await Upload.create(
            user=user,
            description="URL test",
            name="url_file",
            cleanname="url",
            originalname="url",
            ext="jpg",
            size=512,
            type="image/jpeg",
            extra="",
            private=0,
        )

        token = create_access_token({"sub": user.username})
        # Using Bearer token in headers

        response = await client.get(f"/api/v1/files/{upload.id}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        
        # URLs should be absolute
        assert data["get_url"].startswith("http://")
        assert f"/get/{upload.id}/" in data["get_url"]
        assert data["view_url"].startswith("http://")
        assert f"/view/{upload.id}/" in data["view_url"]
        assert data["download_url"].startswith("http://")
        assert f"/download/{upload.id}/" in data["download_url"]

    @pytest.mark.asyncio
    async def test_get_file_metadata_field_name_transformation(self, client):
        """Test that field names are transformed correctly."""
        user = await User.create(
            username="nameuser",
            email="name@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        upload = await Upload.create(
            user=user,
            description="Name test",
            name="name_test",
            cleanname="name",
            originalname="original_name",
            ext="txt",
            size=256,
            type="text/plain",
            extra="",
            private=0,
        )

        token = create_access_token({"sub": user.username})
        # Using Bearer token in headers

        response = await client.get(f"/api/v1/files/{upload.id}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        
        # name should be the original name without extension
        assert data["name"] == "original_name"
        # originalname should include the extension
        assert data["originalname"] == "original_name.txt"

    @pytest.mark.asyncio
    async def test_get_file_metadata_includes_image_data(self, client, tmp_path, monkeypatch):
        """Test that image metadata is included for image uploads."""
        import app.models.uploads
        monkeypatch.setattr(app.models.uploads.config, "storage_path", tmp_path)

        user = await User.create(
            username="imageuser",
            email="image@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        # Create test file
        test_file = tmp_path / f"user_{user.id}" / "test_image.jpg"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake image data")

        upload = await Upload.create(
            user=user,
            description="Image test",
            name="test_image",
            cleanname="test",
            originalname="test",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="",
            private=0,
        )

        # Create image metadata
        await Image.create(
            upload=upload,
            type="image/jpeg",
            width=800,
            height=600,
            bits=8,
            channels=3,
        )

        token = create_access_token({"sub": user.username})
        # Using Bearer token in headers

        response = await client.get(f"/api/v1/files/{upload.id}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        
        assert data["is_image"] is True
        assert "image" in data  # Should have singular "image" not plural "images"
        assert isinstance(data["image"], list)
        assert len(data["image"]) == 1
        assert data["image"][0]["width"] == 800
        assert data["image"][0]["height"] == 600

    @pytest.mark.asyncio
    async def test_get_file_metadata_404_for_nonexistent_file(self, client):
        """Test that getting metadata for non-existent file returns 404."""
        user = await User.create(
            username="notfounduser",
            email="notfound@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        token = create_access_token({"sub": user.username})

        # Try to get non-existent file with authentication
        response = await client.get(
            "/api/v1/files/99999",
            headers={"Authorization": f"Bearer {token}"}
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_file_metadata_403_for_private_file(self, client):
        """Test that accessing another user's private file returns 403."""
        owner = await User.create(
            username="privateowner",
            email="private@example.com",
            password="password",
            fingerprint_hash="fp-hash-owner",
        )

        other_user = await User.create(
            username="otheruser",
            email="other@example.com",
            password="password",
            fingerprint_hash="fp-hash-other",
        )

        upload = await Upload.create(
            user=owner,
            description="Private file",
            name="private_file",
            cleanname="private",
            originalname="private",
            ext="txt",
            size=512,
            type="text/plain",
            extra="",
            private=1,
        )

        # Authenticate as different user
        token = create_access_token({"sub": other_user.username})
        # Using Bearer token in headers

        response = await client.get(f"/api/v1/files/{upload.id}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_file_metadata_allows_owner_access_to_private_file(self, client):
        """Test that owner can access their own private file metadata."""
        user = await User.create(
            username="ownerprivate",
            email="ownerprivate@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        upload = await Upload.create(
            user=user,
            description="Owner's private file",
            name="owner_private",
            cleanname="ownerprivate",
            originalname="ownerprivate",
            ext="doc",
            size=4096,
            type="application/msword",
            extra="",
            private=1,
        )

        token = create_access_token({"sub": user.username})
        # Using Bearer token in headers

        response = await client.get(f"/api/v1/files/{upload.id}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["is_owner"] is True
        assert data["is_private"] is True

    @pytest.mark.asyncio
    async def test_get_file_metadata_allows_public_file_access(self, client):
        """Test that any authenticated user can access public file metadata."""
        owner = await User.create(
            username="publicowner",
            email="publicowner@example.com",
            password="password",
            fingerprint_hash="fp-hash-public",
        )

        other_user = await User.create(
            username="publicviewer",
            email="viewer@example.com",
            password="password",
            fingerprint_hash="fp-hash-viewer",
        )

        upload = await Upload.create(
            user=owner,
            description="Public file",
            name="public_file",
            cleanname="public",
            originalname="public",
            ext="png",
            size=2048,
            type="image/png",
            extra="",
            private=0,
        )

        # Authenticate as different user
        token = create_access_token({"sub": other_user.username})
        # Using Bearer token in headers

        response = await client.get(f"/api/v1/files/{upload.id}", headers={"Authorization": f"Bearer {token}"})

        assert response.status_code == 200
        data = response.json()
        assert data["is_owner"] is False
        assert data["is_private"] is False

    @pytest.mark.asyncio
    async def test_get_file_metadata_requires_authentication(self, client):
        """Test that endpoint requires authentication."""
        user = await User.create(
            username="authtest",
            email="authtest@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        upload = await Upload.create(
            user=user,
            description="Auth test",
            name="auth_test",
            cleanname="auth",
            originalname="auth",
            ext="txt",
            size=128,
            type="text/plain",
            extra="",
            private=0,
        )

        # Try without authentication
        response = await client.get(f"/api/v1/files/{upload.id}")

        # Should return 401
        assert response.status_code == 401
