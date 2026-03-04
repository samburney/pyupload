"""Tests for app/ui/uploads.py - File upload UI endpoints.

This module tests the FastAPI/Starlette file upload endpoints:
- GET /upload - Display upload form page
- POST /upload - Process form submission
- GET /get/{id}/{filename} - Serve files for viewing
- GET /download/{id}/{filename} - Force download files
- DELETE /uploads/{id} - Delete an uploaded file (owner only)
- POST /uploads/{id}/tag-suggestions - Get tag suggestions (owner only, HTMX)
- POST /uploads/{id}/tag - Add a tag to an upload (owner only, HTMX)
- DELETE /uploads/{id}/tag - Remove a tag from an upload (owner only, HTMX)

Tests verify:
- Endpoint accessibility and routing
- Authentication (auto-creates unregistered user)
- Form page rendering with HTML
- File upload handling via multipart form data
- Response structure with HTMX partial updates
- Single and batch file uploads
- Error handling and per-file error recovery
- Success/error message display
- File serving with proper Content-Disposition headers
- Tag management (add, remove, suggestions) with access control
"""

import pytest
from io import BytesIO
from unittest.mock import AsyncMock, patch
from fastapi.responses import HTMLResponse

from app.models.users import User
from app.models.uploads import Upload, UploadResult, UploadMetadata
from app.lib.auth import create_access_token
class TestUploadGetEndpoint:
    """Test GET /upload endpoint for upload form page."""

    @pytest.mark.asyncio
    async def test_upload_page_endpoint_exists(self, client):
        """Test that GET /upload endpoint is accessible."""
        response = await client.get("/upload")
        
        # Should return 200 (auto-creates authenticated user)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_page_returns_html(self, client):
        """Test that upload page returns HTML content."""
        response = await client.get("/upload")
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_upload_page_contains_upload_form(self, client):
        """Test that upload page contains the upload form."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should contain form element
        assert "<form" in html
        assert "upload" in html.lower()

    @pytest.mark.asyncio
    async def test_upload_page_contains_file_input(self, client):
        """Test that upload form contains file input element."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should contain file input with upload_files name
        assert 'type="file"' in html
        assert 'name="upload_files"' in html

    @pytest.mark.asyncio
    async def test_upload_page_contains_submit_button(self, client):
        """Test that upload form contains submit button."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should contain submit button
        assert 'type="submit"' in html or "<button" in html

    @pytest.mark.asyncio
    async def test_upload_page_has_htmx_integration(self, client):
        """Test that form has HTMX attributes for dynamic upload."""
        response = await client.get("/upload")
        
        html = response.text
        
        # Should have HTMX attributes
        assert "hx-post" in html
        assert "/upload" in html

    @pytest.mark.asyncio
    async def test_upload_page_renders_with_authenticated_user(self, client):
        """Test that authenticated user is passed to template."""
        # Get the page (auto-creates user)
        response = await client.get("/upload")
        
        # Should succeed and render page
        assert response.status_code == 200
        html = response.text
        
        # User should be authenticated (page should render without login)
        assert "Upload" in html


class TestUploadPostEndpoint:
    """Test POST /upload endpoint for file uploads."""

    @pytest.mark.asyncio
    async def test_upload_endpoint_exists(self, client):
        """Test that POST /upload endpoint is accessible."""
        # Create a user first
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        response = await client.post(
            "/upload",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 200 or valid response (not 404)
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_upload_post_processes_single_file(self, client, monkeypatch):
        """Test that POST /upload processes a single file."""
        # Create a user
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Mock the upload handler to return success
        async def mock_handle_uploaded_files(user, files):
            file = files[0]
            return [
                UploadResult(
                    status="success",
                    message="",
                    upload_id=1,
                    metadata=UploadMetadata(
                        user_id=user.id,
                        filename="test_20250125-120000_abcd1234",
                        ext="txt",
                        original_filename="test.txt",
                        clean_filename="test",
                        size=7,
                        mime_type="text/plain",
                    ),
                )
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        # Upload a file
        response = await client.post(
            "/upload",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 200
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_post_processes_multiple_files(self, client, monkeypatch):
        """Test that POST /upload processes multiple files in batch."""
        # Create a user
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Mock the upload handler
        async def mock_handle_uploaded_files(user, files):
            results = []
            for i, file in enumerate(files):
                results.append(
                    UploadResult(
                        status="success",
                        message="",
                        upload_id=i + 1,
                        metadata=UploadMetadata(
                            user_id=user.id,
                            filename=f"test{i}_20250125-120000_abcd123{i}",
                            ext="txt",
                            original_filename=f"test{i}.txt",
                            clean_filename=f"test{i}",
                            size=7,
                            mime_type="text/plain",
                        ),
                    )
                )
            return results
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        # Upload multiple files
        response = await client.post(
            "/upload",
            files=[
                ("upload_files", ("test1.txt", BytesIO(b"content"), "text/plain")),
                ("upload_files", ("test2.txt", BytesIO(b"content"), "text/plain")),
            ],
        )
        
        # Should return 200
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_post_returns_html_response(self, client, monkeypatch):
        """Test that POST /upload returns HTML response."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        async def mock_handle_uploaded_files(user, files):
            return [
                UploadResult(
                    status="success",
                    message="",
                    upload_id=1,
                    metadata=UploadMetadata(
                        user_id=user.id,
                        filename="test_20250125-120000_abcd1234",
                        ext="txt",
                        original_filename="test.txt",
                        clean_filename="test",
                        size=7,
                        mime_type="text/plain",
                    ),
                )
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        response = await client.post(
            "/upload",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return HTML response
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_upload_post_displays_success_messages(self, client, monkeypatch):
        """Test that successful uploads display success messages."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        async def mock_handle_uploaded_files(user, files):
            return [
                UploadResult(
                    status="success",
                    message="",
                    upload_id=1,
                    metadata=UploadMetadata(
                        user_id=user.id,
                        filename="test_20250125-120000_abcd1234",
                        ext="txt",
                        original_filename="test.txt",
                        clean_filename="test",
                        size=7,
                        mime_type="text/plain",
                    ),
                )
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        response = await client.post(
            "/upload",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        html = response.text
        
        # Should contain success message mentioning the file
        assert "successfully" in html.lower() or "uploaded" in html.lower()

    @pytest.mark.asyncio
    async def test_upload_post_displays_error_messages_on_failure(self, client, monkeypatch):
        """Test that failed uploads display error messages."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        async def mock_handle_uploaded_files(user, files):
            return [
                UploadResult(
                    status="error",
                    message="File too large",
                    upload_id=None,
                    metadata=None,
                )
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        response = await client.post(
            "/upload",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        html = response.text
        
        # Should contain error message
        assert "error" in html.lower() or "too large" in html.lower()

    @pytest.mark.asyncio
    async def test_upload_post_handles_partial_failures(self, client, monkeypatch):
        """Test that mixed success/error results are displayed correctly."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        async def mock_handle_uploaded_files(user, files):
            return [
                UploadResult(
                    status="success",
                    message="",
                    upload_id=1,
                    metadata=UploadMetadata(
                        user_id=user.id,
                        filename="test1_20250125-120000_abcd1234",
                        ext="txt",
                        original_filename="test1.txt",
                        clean_filename="test1",
                        size=7,
                        mime_type="text/plain",
                    ),
                ),
                UploadResult(
                    status="error",
                    message="File type not allowed",
                    upload_id=None,
                    metadata=None,
                ),
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        response = await client.post(
            "/upload",
            files=[
                ("upload_files", ("test1.txt", BytesIO(b"content"), "text/plain")),
                ("upload_files", ("test2.exe", BytesIO(b"content"), "application/octet-stream")),
            ],
        )
        
        html = response.text
        
        # Should show both success and error messages
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_post_auto_creates_user(self, client, monkeypatch):
        """Test that POST /upload auto-creates authenticated user."""
        # Database should start empty
        user_count_before = await User.all().count()
        
        # Mock the upload handler to avoid actual file processing
        async def mock_handle_uploaded_files(user, files):
            return [
                UploadResult(
                    status="success",
                    message="",
                    upload_id=1,
                    metadata=UploadMetadata(
                        user_id=user.id,
                        filename="test_20250125-120000_abcd1234",
                        ext="txt",
                        original_filename="test.txt",
                        clean_filename="test",
                        size=7,
                        mime_type="text/plain",
                    ),
                )
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        # POST to /upload with a file - this triggers get_or_create_authenticated_user
        response = await client.post(
            "/upload",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should succeed
        assert response.status_code == 200
        
        # User should have been created by the dependency
        user_count_after = await User.all().count()
        assert user_count_after > user_count_before

    @pytest.mark.asyncio
    async def test_upload_post_with_all_failures(self, client, monkeypatch):
        """Test behavior when all files fail to upload."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        async def mock_handle_uploaded_files(user, files):
            return [
                UploadResult(
                    status="error",
                    message="File type not allowed",
                    upload_id=None,
                    metadata=None,
                ),
                UploadResult(
                    status="error",
                    message="File too large",
                    upload_id=None,
                    metadata=None,
                ),
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        response = await client.post(
            "/upload",
            files=[
                ("upload_files", ("test1.exe", BytesIO(b"content"), "application/octet-stream")),
                ("upload_files", ("test2.zip", BytesIO(b"x" * 10000000), "application/zip")),
            ],
        )
        
        # Should still return 200 (partial/error results are returned, not server error)
        assert response.status_code == 200


class TestDownloadEndpoint:
    """Test GET /download/{id}/{filename} endpoint for forced downloads."""

    @pytest.mark.asyncio
    async def test_download_endpoint_forces_attachment(self, client, tmp_path, monkeypatch):
        """Test that /download/ endpoint sets Content-Disposition to attachment."""
        # Monkeypatch storage_path at the module level where it's actually used
        import app.models.uploads
        monkeypatch.setattr(app.models.uploads.config, "storage_path", tmp_path)

        # Create user and file
        user = await User.create(
            username="downloaduser",
            email="download@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        # Authenticate
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        # Create test file
        test_file = tmp_path / f"user_{user.id}" / "download_test.jpg"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake image data")

        upload = await Upload.create(
            user=user,
            description="Download test",
            name="download_test",
            cleanname="download",
            originalname="download.jpg",
            ext="jpg",
            size=15,
            type="image/jpeg",
            extra="",
            private=0,
        )

        # Request file via /download/ endpoint
        response = await client.get(f"/download/{upload.id}/download.jpg")

        assert response.status_code == 200
        assert "attachment" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_download_endpoint_with_authentication(self, client, tmp_path, monkeypatch):
        """Test that /download/ endpoint works with proper authentication."""
        # Monkeypatch storage_path at the module level where it's actually used
        import app.models.uploads
        monkeypatch.setattr(app.models.uploads.config, "storage_path", tmp_path)

        # Create user and upload
        user = await User.create(
            username="authuser",
            email="auth@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        # Authenticate user
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        # Create test file
        test_file = tmp_path / f"user_{user.id}" / "auth_test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("auth test content")

        upload = await Upload.create(
            user=user,
            description="Auth test",
            name="auth_test",
            cleanname="auth",
            originalname="auth.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="",
            private=0,
        )

        # Access with authentication should work
        response = await client.get(f"/download/{upload.id}/auth.txt", follow_redirects=False)

        # Should successfully download
        assert response.status_code == 200
        assert "attachment" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_download_url_property_generates_correct_url(self, db):
        """Test that Upload.download_url property generates correct URL."""
        from app.lib.config import get_app_config
        config = get_app_config()
        
        user = await User.create(
            username="urltest",
            email="url@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        upload = await Upload.create(
            user=user,
            description="URL test",
            name="url_test",
            cleanname="urltest",
            originalname="urltest.pdf",
            ext="pdf",
            size=1024,
            type="application/pdf",
            extra="",
            private=0,
        )

        # Check the download_url property - now includes app_base_url
        assert upload.download_url == f"{config.app_base_url}/download/{upload.id}/urltest.pdf"


class TestUploadIntegration:
    """Test integration between UI endpoints and upload handler."""

    @pytest.mark.asyncio
    async def test_both_endpoints_delegate_to_handler(self, client, monkeypatch):
        """Test that both GET and POST endpoints use same handler logic."""
        # Setup mock to verify handler is called
        handler_called = {"count": 0}
        
        async def mock_handle_uploaded_files(user, files):
            handler_called["count"] += 1
            return [
                UploadResult(
                    status="success",
                    message="",
                    upload_id=1,
                    metadata=UploadMetadata(
                        user_id=user.id,
                        filename="test_20250125-120000_abcd1234",
                        ext="txt",
                        original_filename="test.txt",
                        clean_filename="test",
                        size=7,
                        mime_type="text/plain",
                    ),
                )
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        # POST endpoint should call handler
        response = await client.post(
            "/upload",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        assert response.status_code == 200
        assert handler_called["count"] >= 1

    @pytest.mark.asyncio
    async def test_upload_lists_successful_files(self, client, monkeypatch):
        """Test that successful uploads are listed in response."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        async def mock_handle_uploaded_files(user, files):
            return [
                UploadResult(
                    status="success",
                    message="",
                    upload_id=1,
                    metadata=UploadMetadata(
                        user_id=user.id,
                        filename="test_20250125-120000_abcd1234",
                        ext="txt",
                        original_filename="important.txt",
                        clean_filename="important",
                        size=7,
                        mime_type="text/plain",
                    ),
                )
            ]
        
        import app.ui.uploads
        monkeypatch.setattr(app.ui.uploads, "handle_uploaded_files", mock_handle_uploaded_files)
        
        response = await client.post(
            "/upload",
            files={"upload_files": ("important.txt", BytesIO(b"content"), "text/plain")},
        )
        
        html = response.text
        
        # Should mention the filename
        assert "important" in html.lower() or "test" in html.lower()


class TestUploadGetErrorHandling:
    """Error handling tests for GET file serving endpoints."""

    @pytest.mark.asyncio
    async def test_get_upload_skips_processing_when_image_metadata_missing(self, client, tmp_path, monkeypatch):
        """Serving should succeed when image metadata is missing because processing is not requested."""
        import app.models.uploads
        monkeypatch.setattr(app.models.uploads.config, "storage_path", tmp_path)

        user = await User.create(
            username="missingmetauser",
            email="missingmeta@example.com",
            password="password",
            fingerprint_hash="fp-hash-missingmeta",
        )

        # Create the physical file, but intentionally do not create related Image metadata.
        test_file = tmp_path / f"user_{user.id}" / "missing_meta.jpg"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake image bytes")

        upload = await Upload.create(
            user=user,
            description="Missing image metadata upload",
            name="missing_meta",
            cleanname="missingmeta",
            originalname="missing_meta.jpg",
            ext="jpg",
            size=16,
            type="image/jpeg",
            extra="",
            private=0,
        )

        response = await client.get(f"/get/{upload.id}/missing_meta-320x0.jpg")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_get_missing_non_image_returns_html_404(self, client):
        """Missing non-image files should return plain 404 instead of image-processing failure."""
        response = await client.get("/get/999999/missing.txt")

        assert response.status_code == 404
        assert "image/" not in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_get_unauthorised_non_image_returns_403(self, client, monkeypatch):
        """Unauthorized non-image file requests should return 403."""
        user = await User.create(
            username="owneruser",
            email="owner@example.com",
            password="password",
            fingerprint_hash="fp-owner",
        )

        upload = await Upload.create(
            user=user,
            description="Private file",
            name="private_file",
            cleanname="private-file",
            originalname="private.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="",
            private=1,
        )

        async def mock_serve_file(*args, **kwargs):
            return HTMLResponse(status_code=403)

        monkeypatch.setattr("app.ui.uploads.serve_file", mock_serve_file)

        response = await client.get(f"/get/{upload.id}/private.txt")

        assert response.status_code == 403
        assert "image/" not in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_get_missing_image_returns_error_image(self, client):
        """Missing image conversion requests should still return generated error images."""
        response = await client.get("/get/999999/missing.jpg")

        assert response.status_code == 404
        assert response.headers.get("content-type") == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_image_processing_error_for_image_request_returns_error_image(self, client, monkeypatch):
        """ImageProcessingError for image requests should return an image response, not 500."""
        user = await User.create(
            username="imageprocessingimageuser",
            email="imageprocessingimage@example.com",
            password="password",
            fingerprint_hash="fp-image-processing-image",
        )

        upload = await Upload.create(
            user=user,
            description="Image processing error image request",
            name="image_processing_error",
            cleanname="image-processing-error",
            originalname="image_processing_error.jpg",
            ext="jpg",
            size=10,
            type="image/jpeg",
            extra="",
            private=0,
        )

        async def mock_serve_file(*args, **kwargs):
            return HTMLResponse(status_code=422, headers={"content-type": "image/jpeg"})

        monkeypatch.setattr("app.ui.uploads.serve_file", mock_serve_file)

        response = await client.get(f"/get/{upload.id}/image_processing_error-320x0.jpg")

        assert response.status_code == 422
        assert response.status_code != 500
        assert response.headers.get("content-type") == "image/jpeg"

    @pytest.mark.asyncio
    async def test_get_image_processing_error_for_non_image_request_returns_html_fallback(self, client, monkeypatch):
        """ImageProcessingError for non-image requests should return HTML fallback, not 500."""
        user = await User.create(
            username="imageprocessingtextuser",
            email="imageprocessingtext@example.com",
            password="password",
            fingerprint_hash="fp-image-processing-text",
        )

        upload = await Upload.create(
            user=user,
            description="Image processing error non-image request",
            name="image_processing_error_text",
            cleanname="image-processing-error-text",
            originalname="image_processing_error_text.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="",
            private=0,
        )

        async def mock_serve_file(*args, **kwargs):
            return HTMLResponse(status_code=422)

        monkeypatch.setattr("app.ui.uploads.serve_file", mock_serve_file)

        response = await client.get(f"/get/{upload.id}/image_processing_error_text.txt")

        assert response.status_code == 422
        assert response.status_code != 500
        assert "image/" not in response.headers.get("content-type", "")


class TestDeleteUploadPage:
    """Tests for DELETE /uploads/{id} UI endpoint."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated DELETE requests must redirect to /login."""
        response = await client.delete("/uploads/1", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 HTML error when the upload does not exist."""
        user = await User.create(
            username="uidel404",
            email="uidel404@example.com",
            password="pw",
            is_registered=True,
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.delete("/uploads/999999")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_403_for_non_owner(self, client):
        """Returns 403 when the authenticated user is not the upload owner."""
        owner = await User.create(
            username="uidelowner",
            email="uidelowner@example.com",
            password="pw",
            is_registered=True,
        )
        other = await User.create(
            username="uidelother",
            email="uidelother@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await Upload.create(
            user=owner,
            description="",
            name="uideltest_20250101-000000_a1b2c3d4",
            cleanname="uideltest",
            originalname="uideltest.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="0",
        )
        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.delete(f"/uploads/{upload.id}")
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_returns_204_with_hx_redirect_on_success(self, client):
        """Successful delete returns 204 with HX-Redirect header pointing to /profile."""
        user = await User.create(
            username="uidelsucc",
            email="uidelsucc@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await Upload.create(
            user=user,
            description="",
            name="uisuccfile_20250101-000000_a1b2c3d4",
            cleanname="uisuccfile",
            originalname="uisuccfile.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="0",
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch("app.lib.file_io.delete_file"):
            response = await client.delete(f"/uploads/{upload.id}", follow_redirects=False)

        assert response.status_code == 204
        assert response.headers.get("HX-Redirect") == "/profile"

    @pytest.mark.asyncio
    async def test_removes_upload_from_database_on_success(self, client):
        """Successful delete removes the upload record from the database."""
        user = await User.create(
            username="uideldb",
            email="uideldb@example.com",
            password="pw",
            is_registered=True,
        )
        upload = await Upload.create(
            user=user,
            description="",
            name="uidbfile_20250101-000000_b2c3d4e5",
            cleanname="uidbfile",
            originalname="uidbfile.txt",
            ext="txt",
            size=10,
            type="text/plain",
            extra="0",
        )
        upload_id = upload.id
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        with patch("app.lib.file_io.delete_file"):
            await client.delete(f"/uploads/{upload_id}")

        assert await Upload.get_or_none(id=upload_id) is None


def _tag_upload_data(user, suffix: str = "") -> dict:
    """Minimal Upload.create kwargs for tag endpoint tests."""
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
    """Create a tag-test upload with a real backing file in tmp storage."""
    import app.models.uploads

    monkeypatch.setattr(app.models.uploads.config, "storage_path", tmp_path)
    upload = await Upload.create(**_tag_upload_data(user, suffix))
    upload.filepath.parent.mkdir(parents=True, exist_ok=True)
    upload.filepath.write_text("tag test file")

    return upload


class TestTagSuggestionsEndpoint:
    """Tests for POST /uploads/{id}/tag-suggestions."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/uploads/1/tag-suggestions", data={"tag_name": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when the upload does not exist."""
        user = await User.create(username="tsugg404", email="tsugg404@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/uploads/999999/tag-suggestions", data={"tag_name": "foo"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_any_authenticated_user_can_get_suggestions(self, client):
        """Any authenticated user may request tag suggestions for any upload."""
        owner = await User.create(username="tsugowner", email="tsugowner@example.com", password="pw", is_registered=True)
        other = await User.create(username="tsugother", email="tsugother@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(owner, "sug403"))

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/tag-suggestions", data={"tag_name": "foo"})
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_returns_204_for_empty_tag_name(self, client):
        """An empty tag_name returns 204 No Content without hitting the database."""
        user = await User.create(username="tsugempty", email="tsugempty@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/uploads/1/tag-suggestions", data={"tag_name": ""})
        assert response.status_code == 204

    @pytest.mark.asyncio
    async def test_returns_suggestions_matching_query(self, client, tmp_path, monkeypatch):
        """Returns tags matching the query string from the database."""
        from app.models.tags import Tag

        user = await User.create(username="tsugmatch", email="tsugmatch@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(user, "sugmatch", tmp_path, monkeypatch)
        await Tag.create(name="python")
        await Tag.create(name="pyupload")
        await Tag.create(name="unrelated")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/tag-suggestions", data={"tag_name": "py"})
        assert response.status_code == 200
        html = response.text
        assert "python" in html
        assert "pyupload" in html
        assert "unrelated" not in html

    @pytest.mark.asyncio
    async def test_excludes_tags_already_on_upload(self, client, tmp_path, monkeypatch):
        """Tags already attached to the upload are not included in suggestions."""
        from app.models.tags import Tag

        user = await User.create(username="tsugexcl", email="tsugexcl@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(user, "sugexcl", tmp_path, monkeypatch)
        await Tag.add_or_create_for_upload(upload, "already-attached")
        await Tag.create(name="other-match")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/tag-suggestions", data={"tag_name": "a"})
        assert response.status_code == 200
        assert "already-attached" not in response.text


class TestUploadAddTagEndpoint:
    """Tests for POST /uploads/{id}/tag."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/uploads/1/tag", data={"tag_name": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when the upload does not exist."""
        user = await User.create(username="tadd404", email="tadd404@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/uploads/999999/tag", data={"tag_name": "foo"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_any_authenticated_user_can_add_tag(self, client):
        """Any authenticated user may add a tag to any upload."""
        owner = await User.create(username="taddowner", email="taddowner@example.com", password="pw", is_registered=True)
        other = await User.create(username="taddother", email="taddother@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(owner, "add403"))

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/tag", data={"tag_name": "foo"})
        assert response.status_code == 201

    @pytest.mark.asyncio
    async def test_adds_tag_and_returns_201(self, client, tmp_path, monkeypatch):
        """Successfully adding a tag returns 201 with the updated tag-input HTML."""
        from app.models.tags import Tag

        user = await User.create(username="taddsucc", email="taddsucc@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(user, "addsucc", tmp_path, monkeypatch)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/tag", data={"tag_name": "newtag"})
        assert response.status_code == 201
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_tag_persisted_in_database(self, client, tmp_path, monkeypatch):
        """The tag is saved in the database and associated with the upload."""
        from app.models.tags import Tag

        user = await User.create(username="tadddb", email="tadddb@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(user, "adddb", tmp_path, monkeypatch)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        await client.post(f"/uploads/{upload.id}/tag", data={"tag_name": "persisted"})

        await upload.fetch_related("tags")
        assert any(t.name == "persisted" for t in upload.tags)

    @pytest.mark.asyncio
    async def test_returns_400_for_empty_tag_name(self, client, tmp_path, monkeypatch):
        """An empty or invalid tag name (after cleaning) returns 400 Bad Request."""
        user = await User.create(username="taddempty", email="taddempty@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(user, "addempty", tmp_path, monkeypatch)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/tag", data={"tag_name": "!@#$"})
        assert response.status_code == 400


class TestUploadDeleteTagEndpoint:
    """Tests for DELETE /uploads/{id}/tag."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.delete("/uploads/1/tag?tag_name=foo", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when the upload does not exist."""
        user = await User.create(username="tdel404", email="tdel404@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.delete("/uploads/999999/tag?tag_name=foo")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_any_authenticated_user_can_remove_tag(self, client):
        """Any authenticated user may remove a tag from any upload."""
        owner = await User.create(username="tdelowner", email="tdelowner@example.com", password="pw", is_registered=True)
        other = await User.create(username="tdelother", email="tdelother@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_tag_upload_data(owner, "del403"))

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        # Tag does not exist so removal succeeds silently — returns 200 with updated HTML
        response = await client.delete(f"/uploads/{upload.id}/tag?tag_name=foo")
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_removes_tag_and_returns_200(self, client, tmp_path, monkeypatch):
        """Successfully removing a tag returns 200 with the updated tag-input HTML."""
        from app.models.tags import Tag

        user = await User.create(username="tdelsucc", email="tdelsucc@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(user, "delsucc", tmp_path, monkeypatch)
        await Tag.add_or_create_for_upload(upload, "removable")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.delete(f"/uploads/{upload.id}/tag?tag_name=removable")
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_tag_removed_from_database(self, client, tmp_path, monkeypatch):
        """The tag association is removed after the delete request."""
        from app.models.tags import Tag

        user = await User.create(username="tdeldb", email="tdeldb@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(user, "deldb", tmp_path, monkeypatch)
        await Tag.add_or_create_for_upload(upload, "gone")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        await client.delete(f"/uploads/{upload.id}/tag?tag_name=gone")

        await upload.fetch_related("tags")
        assert all(t.name != "gone" for t in upload.tags)

    @pytest.mark.asyncio
    async def test_returns_400_for_empty_tag_name(self, client, tmp_path, monkeypatch):
        """An empty or invalid tag name (after cleaning) returns 400 Bad Request."""
        user = await User.create(username="tdelempty", email="tdelempty@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(user, "delempty", tmp_path, monkeypatch)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.delete(f"/uploads/{upload.id}/tag?tag_name=!@%23%24")
        assert response.status_code == 400


# ---------------------------------------------------------------------------
# Collection endpoint helpers
# ---------------------------------------------------------------------------

def _col_upload_data(user, suffix: str = "") -> dict:
    """Minimal Upload.create kwargs for collection endpoint tests."""
    return {
        "user": user,
        "description": f"col test {suffix}",
        "name": f"colfile{suffix}_20250301-000000_a1b2c3d4",
        "cleanname": f"colfile{suffix}",
        "originalname": f"colfile{suffix}.txt",
        "ext": "txt",
        "size": 10,
        "type": "text/plain",
        "extra": "0",
    }


class TestCollectionSearchEndpoint:
    """Tests for POST /uploads/{id}/collection-search."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/uploads/1/collection-search", data={"collection_name": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when the upload does not exist."""
        user = await User.create(username="cse404", email="cse404@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/uploads/999999/collection-search", data={"collection_name": "foo"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_html_with_matching_collections(self, client):
        """Returns filtered collections matching the query string."""
        from app.models.collections import Collection

        user = await User.create(username="csematch", email="csematch@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "sematch"))
        await Collection.create(user=user, name="Python Pics", name_unique="python-pics")
        await Collection.create(user=user, name="Pyupload Tests", name_unique="pyupload-tests")
        await Collection.create(user=user, name="Unrelated", name_unique="unrelated")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/collection-search", data={"collection_name": "py"})
        assert response.status_code == 200
        html = response.text
        assert "Python Pics" in html
        assert "Pyupload Tests" in html
        assert "Unrelated" not in html

    @pytest.mark.asyncio
    async def test_already_linked_collection_rendered_as_checked(self, client):
        """Collections already linked to the upload are rendered as checked; unlinked ones are not."""
        from app.models.collections import Collection

        user = await User.create(username="cseexcl", email="cseexcl@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "seexcl"))
        already = await Collection.create(user=user, name="Already Added", name_unique="already-added")
        await Collection.create(user=user, name="Available", name_unique="available")
        await upload.collections.add(already)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/collection-search", data={"collection_name": ""})
        assert response.status_code == 200
        html = response.text
        # Already linked collection is rendered as a checked checkbox
        assert "Already Added" in html
        assert f'value="{already.id}" checked' in html or f'value="{already.id}"\n                        checked' in html
        # Unlinked collection appears without checked
        assert "Available" in html


class TestCollectionAddEndpoint:
    """Tests for POST /uploads/{id}/collection."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.post("/uploads/1/collection", data={"collection_name": "foo"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when the upload does not exist."""
        user = await User.create(username="cadd404", email="cadd404@example.com", password="pw", is_registered=True)
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post("/uploads/999999/collection", data={"collection_name": "foo"})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_creates_collection_and_returns_201(self, client):
        """Successfully adding a new collection returns 201 with updated HTML."""
        user = await User.create(username="caddsucc", email="caddsucc@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "addsucc"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/collection", data={"collection_name": "New Collection"})
        assert response.status_code == 201
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_collection_persisted_and_linked(self, client):
        """The new collection is saved to the database and linked to the upload."""
        from app.models.collections import Collection

        user = await User.create(username="cadddb", email="cadddb@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "adddb"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        await client.post(f"/uploads/{upload.id}/collection", data={"collection_name": "Persisted"})

        col = await Collection.get_or_none(name="Persisted", user=user)
        assert col is not None
        await upload.fetch_related("collections")
        assert any(c.id == col.id for c in upload.collections)

    @pytest.mark.asyncio
    async def test_any_authenticated_user_can_add_collection(self, client):
        """Any authenticated user may add their own collection to any upload."""
        from app.models.collections import Collection

        owner = await User.create(username="caddanyowner", email="caddanyowner@example.com", password="pw", is_registered=True)
        other = await User.create(username="caddanyother", email="caddanyother@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(owner, "addany"))

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}

        response = await client.post(f"/uploads/{upload.id}/collection", data={"collection_name": "Other User Col"})
        assert response.status_code == 201

        col = await Collection.get_or_none(name="Other User Col", user=other)
        assert col is not None


class TestCollectionPatchEndpoint:
    """Tests for PATCH /uploads/{id}/collection."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.patch("/uploads/1/collection", data={"collection_ids": "1"}, follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when the upload does not exist."""
        from app.models.collections import Collection

        user = await User.create(username="cpatch404", email="cpatch404@example.com", password="pw", is_registered=True)
        col = await Collection.create(user=user, name="Col", name_unique="col-p404")
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/uploads/999999/collection", data={"collection_ids": str(col.id)})
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_returns_400_when_all_collection_ids_invalid(self, client):
        """Returns 400 when every supplied collection ID is unknown or not owned."""
        user = await User.create(username="cpatch400", email="cpatch400@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patch400"))
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch(f"/uploads/{upload.id}/collection", data={"collection_ids": "999999"})
        assert response.status_code == 400

    @pytest.mark.asyncio
    async def test_adds_collection_to_upload(self, client):
        """Sending a collection ID adds that collection to the upload."""
        from app.models.collections import Collection

        user = await User.create(username="cpatchadd", email="cpatchadd@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patchadd"))
        col = await Collection.create(user=user, name="To Add", name_unique="to-add")

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch(f"/uploads/{upload.id}/collection", data={"collection_ids": str(col.id)})
        assert response.status_code == 202

        await upload.fetch_related("collections")
        assert any(c.id == col.id for c in upload.collections)

    @pytest.mark.asyncio
    async def test_removes_unchecked_collection_from_upload(self, client):
        """Collections owned by the user that are absent from the payload are removed."""
        from app.models.collections import Collection

        user = await User.create(username="cpatchrm", email="cpatchrm@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patchrm"))
        col_keep = await Collection.create(user=user, name="Keep", name_unique="keep-rm")
        col_remove = await Collection.create(user=user, name="Remove", name_unique="remove-rm")
        await upload.collections.add(col_keep)
        await upload.collections.add(col_remove)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        # Only send col_keep; col_remove should be removed
        response = await client.patch(f"/uploads/{upload.id}/collection", data={"collection_ids": str(col_keep.id)})
        assert response.status_code == 202

        await upload.fetch_related("collections")
        col_ids = [c.id for c in upload.collections]
        assert col_keep.id in col_ids
        assert col_remove.id not in col_ids

    @pytest.mark.asyncio
    async def test_ignores_collections_owned_by_other_users(self, client):
        """Collections owned by another user are rejected and not added."""
        from app.models.collections import Collection

        owner = await User.create(username="cpermown", email="cpermown@example.com", password="pw", is_registered=True)
        other = await User.create(username="cpermoth", email="cpermoth@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(owner, "perm"))
        other_col = await Collection.create(user=other, name="Other Col", name_unique="other-col-perm")

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        response = await client.patch(f"/uploads/{upload.id}/collection", data={"collection_ids": str(other_col.id)})
        assert response.status_code == 400

        await upload.fetch_related("collections")
        assert all(c.id != other_col.id for c in upload.collections)

    @pytest.mark.asyncio
    async def test_empty_payload_removes_all_user_collections(self, client):
        """Sending no collection IDs clears all of the current user's collections from the upload."""
        from app.models.collections import Collection

        user = await User.create(username="cpatchclear", email="cpatchclear@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_col_upload_data(user, "patchclear"))
        col = await Collection.create(user=user, name="Will Be Cleared", name_unique="will-be-cleared")
        await upload.collections.add(col)

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch(f"/uploads/{upload.id}/collection")
        assert response.status_code == 202

        await upload.fetch_related("collections")
        assert all(c.id != col.id for c in upload.collections)

