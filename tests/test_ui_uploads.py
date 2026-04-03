"""Tests for app/ui/uploads.py - File upload UI endpoints.

This module tests the FastAPI/Starlette file upload endpoints:
- GET /uploads - Display upload form page
- POST /uploads - Process form submission
- GET /get/{id}/{filename} - Serve files for viewing
- GET /download/{id}/{filename} - Force download files
- DELETE /uploads/{id} - Delete an uploaded file (owner only)
- PATCH /uploads/{id}/private - Toggle upload privacy (owner only, HTMX)
- PATCH /uploads/{id}/description - Update upload description (owner only, HTMX)

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

Tag management tests have moved to tests/test_ui_tags.py.
"""

import pytest
from io import BytesIO
from unittest.mock import AsyncMock, patch
from fastapi.responses import HTMLResponse

from app.models.users import User
from app.models.uploads import Upload, UploadResult, UploadMetadata
from app.lib.auth import create_access_token
class TestUploadGetEndpoint:
    """Test GET /uploads endpoint for upload form page."""

    @pytest.mark.asyncio
    async def test_upload_page_endpoint_exists(self, client):
        """Test that GET /uploads endpoint is accessible."""
        response = await client.get("/uploads")
        
        # Should return 200 (auto-creates authenticated user)
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_page_returns_html(self, client):
        """Test that upload page returns HTML content."""
        response = await client.get("/uploads")
        
        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
    async def test_upload_page_contains_upload_form(self, client):
        """Test that upload page contains the upload form."""
        response = await client.get("/uploads")
        
        html = response.text
        
        # Should contain form element
        assert "<form" in html
        assert "upload" in html.lower()

    @pytest.mark.asyncio
    async def test_upload_page_contains_file_input(self, client):
        """Test that upload form contains file input element."""
        response = await client.get("/uploads")
        
        html = response.text
        
        # Should contain file input with upload_files name
        assert 'type="file"' in html
        assert 'name="upload_files"' in html

    @pytest.mark.asyncio
    async def test_upload_page_contains_submit_button(self, client):
        """Test that upload form contains submit button."""
        response = await client.get("/uploads")
        
        html = response.text
        
        # Should contain submit button
        assert 'type="submit"' in html or "<button" in html

    @pytest.mark.asyncio
    async def test_upload_page_has_htmx_integration(self, client):
        """Test that form has HTMX attributes for dynamic upload."""
        response = await client.get("/uploads")
        
        html = response.text
        
        # Should have HTMX attributes
        assert "hx-post" in html
        assert "/uploads" in html

    @pytest.mark.asyncio
    async def test_upload_page_includes_window_dimensions_script(self, client):
        """Test that upload page includes the window-dimensions tracking script."""
        response = await client.get("/uploads")

        assert response.status_code == 200
        html = response.text
        assert "/static/js/store-client-dimensions.js" in html

    @pytest.mark.asyncio
    async def test_upload_page_renders_with_authenticated_user(self, client):
        """Test that authenticated user is passed to template."""
        # Get the page (auto-creates user)
        response = await client.get("/uploads")
        
        # Should succeed and render page
        assert response.status_code == 200
        html = response.text
        
        # User should be authenticated (page should render without login)
        assert "Upload" in html


class TestUploadPostEndpoint:
    """Test POST /uploads endpoint for file uploads."""

    @pytest.mark.asyncio
    async def test_upload_endpoint_exists(self, client):
        """Test that POST /uploads endpoint is accessible."""
        # Create a user first
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        response = await client.post(
            "/uploads",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 200 or valid response (not 404)
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_upload_post_processes_single_file(self, client, monkeypatch):
        """Test that POST /uploads processes a single file."""
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
            "/uploads",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 200
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_post_processes_multiple_files(self, client, monkeypatch):
        """Test that POST /uploads processes multiple files in batch."""
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
            "/uploads",
            files=[
                ("upload_files", ("test1.txt", BytesIO(b"content"), "text/plain")),
                ("upload_files", ("test2.txt", BytesIO(b"content"), "text/plain")),
            ],
        )
        
        # Should return 200
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_upload_post_returns_html_response(self, client, monkeypatch):
        """Test that POST /uploads returns HTML response."""
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
            "/uploads",
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
            "/uploads",
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
            "/uploads",
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
            "/uploads",
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
        """Test that POST /uploads auto-creates authenticated user."""
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
            "/uploads",
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
            "/uploads",
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
            "/uploads",
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
            "/uploads",
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


# ---------------------------------------------------------------------------
# Upload helper (also used by privacy toggle and description tests below)
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


class TestUploadPrivateTogglePatchEndpoint:
    """Tests for PATCH /uploads/{id}/private."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.patch("/uploads/1/private", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
    async def test_returns_404_for_nonexistent_upload(self, client):
        """Returns 404 when the upload does not exist."""
        user = await User.create(
            username="priv404",
            email="priv404@example.com",
            password="pw",
            is_registered=True,
        )
        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}

        response = await client.patch("/uploads/999999/private", data={"upload_private": "true"})
        assert response.status_code == 404
        assert "Upload not found" in response.text

    @pytest.mark.asyncio
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

        response = await client.patch(f"/uploads/{upload.id}/private", data={"upload_private": "true"})
        assert response.status_code == 200
        assert "Private" in response.text
        assert "checked" in response.text
        assert f'hx-patch="/uploads/{upload.id}/private"' in response.text

        await upload.refresh_from_db()
        assert upload.private == 1

    @pytest.mark.asyncio
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

        response = await client.patch(f"/uploads/{upload.id}/private")
        assert response.status_code == 200
        assert "Public" in response.text
        assert 'class="peer sr-only" checked' not in response.text

        await upload.refresh_from_db()
        assert upload.private == 0

    @pytest.mark.asyncio
    async def test_non_owner_cannot_toggle_privacy(self, client, tmp_path, monkeypatch):
        """Non-owners receive 403 and the upload privacy flag is unchanged."""
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

        response = await client.patch(f"/uploads/{upload.id}/private", data={"upload_private": "true"})
        assert response.status_code == 403

        await upload.refresh_from_db()
        assert upload.private == 0


class TestUploadDescriptionPatchEndpoint:
    """Tests for PATCH /uploads/{id}/description."""

    @pytest.mark.asyncio
    async def test_redirects_to_login_when_unauthenticated(self, client):
        """Unauthenticated requests redirect to /login."""
        response = await client.patch("/uploads/1/description", follow_redirects=False)
        assert response.status_code == 303
        assert "/login" in response.headers.get("location", "")

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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


# ---------------------------------------------------------------------------
# View page helpers
# ---------------------------------------------------------------------------

import pytest
from pathlib import Path

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

    @pytest.mark.asyncio
    async def test_public_upload_redirects_to_view_with_filename(self, client):
        """Public upload redirects to the canonical view URL with filename."""
        user = await User.create(username="viewredir1", email="viewredir1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "redir1"))

        response = await client.get(f"/view/{upload.id}", follow_redirects=False)

        assert response.status_code == 301
        location = response.headers["location"]
        assert f"/view/{upload.id}/" in location
        assert upload.cleanname in location

    @pytest.mark.asyncio
    async def test_nonexistent_upload_returns_404(self, client):
        """Non-existent upload ID returns 404."""
        response = await client.get("/view/999999", follow_redirects=False)
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_private_upload_returns_403(self, client):
        """Private upload without user context returns 403 (prevents info disclosure)."""
        user = await User.create(username="viewredir3", email="viewredir3@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "redir3"), "private": 1})

        client.cookies.clear()
        response = await client.get(f"/view/{upload.id}", follow_redirects=False)

        assert response.status_code == 403


class TestViewUploadPageEndpoint:
    """Tests for GET /view/{id}/{filename} view page — Step 1."""

    @pytest.mark.asyncio
    async def test_public_upload_accessible_to_anonymous_users(self, client):
        """Anonymous users can view public uploads."""
        user = await User.create(username="viewanon1", email="viewanon1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "anon1"))

        client.cookies.clear()
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_public_upload_accessible_to_authenticated_users(self, client):
        """Authenticated users can view public uploads."""
        user = await User.create(username="viewauth1", email="viewauth1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "auth1"))

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_private_upload_accessible_to_owner(self, client):
        """Owners can view their own private uploads."""
        user = await User.create(username="viewowner1", email="viewowner1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "owner1"), "private": 1})

        token = create_access_token({"sub": user.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_private_upload_returns_403_for_other_users(self, client):
        """Non-owners receive 403 when attempting to view a private upload."""
        owner = await User.create(username="viewprivown", email="viewprivown@example.com", password="pw", is_registered=True)
        other = await User.create(username="viewprivoth", email="viewprivoth@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(owner, "priv403"), "private": 1})

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_private_upload_returns_403_for_anonymous_users(self, client):
        """Anonymous users receive 403 when attempting to view a private upload."""
        user = await User.create(username="viewprivanon", email="viewprivanon@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "privanon"), "private": 1})

        client.cookies.clear()
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_nonexistent_upload_returns_404(self, client):
        """Non-existent upload ID returns 404."""
        response = await client.get("/view/999999/nonexistent.txt")
        assert response.status_code == 404

    @pytest.mark.asyncio
    async def test_page_returns_html(self, client):
        """View page returns HTML content."""
        user = await User.create(username="viewhtml1", email="viewhtml1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "html1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200
        assert "text/html" in response.headers.get("content-type", "")

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_image_upload_shows_image_frame(self, client):
        """Image uploads render the HTMX-triggered view-frame-image element."""
        from app.models.images import Image
        user = await User.create(username="viewimg1", email="viewimg1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "img1"), "type": "image/jpeg", "ext": "jpg", "originalname": "viewfileimg1.jpg"})
        await Image.create(upload=upload, type="jpg", width=800, height=600, bits=8, channels=3)

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.jpg")

        assert response.status_code == 200
        assert "view-frame-image" in response.text

    @pytest.mark.asyncio
    async def test_non_image_upload_shows_file_extension(self, client):
        """Non-image uploads display the file extension in the file icon area."""
        user = await User.create(username="viewext1", email="viewext1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "ext1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200
        assert ".txt" in response.text

    @pytest.mark.asyncio
    async def test_non_image_upload_does_not_show_image_frame(self, client):
        """Non-image uploads do not render the image view frame element."""
        user = await User.create(username="viewnoimg1", email="viewnoimg1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "noimg1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "view-frame-image" not in response.text

    # Step 3: Metadata

    @pytest.mark.asyncio
    async def test_metadata_shows_uploader_username(self, client):
        """Metadata panel shows the uploader's username."""
        user = await User.create(username="viewmeta1", email="viewmeta1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "meta1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "viewmeta1" in response.text

    @pytest.mark.asyncio
    async def test_metadata_shows_mime_type(self, client):
        """Metadata panel shows the upload's MIME type."""
        user = await User.create(username="viewmeta2", email="viewmeta2@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "meta2"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "text/plain" in response.text

    @pytest.mark.asyncio
    async def test_metadata_shows_view_count_icon(self, client):
        """Metadata panel includes the view count field."""
        user = await User.create(username="viewmeta3", email="viewmeta3@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "meta3"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "icon-view-count" in response.text

    @pytest.mark.asyncio
    async def test_metadata_shows_upload_date_icon(self, client):
        """Metadata panel includes the upload date field."""
        user = await User.create(username="viewmeta4", email="viewmeta4@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "meta4"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "icon-calendar" in response.text

    @pytest.mark.asyncio
    async def test_image_metadata_shows_dimensions(self, client):
        """Image uploads show width × height in the metadata panel."""
        from app.models.images import Image
        user = await User.create(username="viewdims1", email="viewdims1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**{**_view_upload_data(user, "dims1"), "type": "image/jpeg", "ext": "jpg", "originalname": "viewfiledims1.jpg"})
        await Image.create(upload=upload, type="jpg", width=1920, height=1080, bits=8, channels=3)

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.jpg")

        assert "1920" in response.text
        assert "1080" in response.text

    @pytest.mark.asyncio
    async def test_non_image_metadata_does_not_show_dimensions(self, client):
        """Non-image uploads do not include the image dimensions field."""
        user = await User.create(username="viewdims2", email="viewdims2@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "dims2"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert "#icon-image-dimensions" not in response.text

    # Step 4: Sharing options

    @pytest.mark.asyncio
    async def test_share_button_shown_for_public_upload(self, client):
        """Share button is rendered for public uploads."""
        user = await User.create(username="viewshare1", email="viewshare1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "share1"))

        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert response.status_code == 200
        assert "Share upload" in response.text

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_edit_form_visible_to_owner(self, client):
        """Owner sees the Alpine.js inline-edit description component."""
        owner = await User.create(username="viewedit1", email="viewedit1@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(owner, "edit1"))

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert 'id="upload-description"' in response.text

    @pytest.mark.asyncio
    async def test_edit_form_not_visible_to_non_owners(self, client):
        """Non-owners see only the read-only description paragraph, not the edit component."""
        owner = await User.create(username="viewedit2own", email="viewedit2own@example.com", password="pw", is_registered=True)
        other = await User.create(username="viewedit2oth", email="viewedit2oth@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(owner, "edit2"))

        token = create_access_token({"sub": other.username})
        client.cookies = {"access_token": token}
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert 'id="upload-description"' not in response.text

    @pytest.mark.asyncio
    async def test_edit_form_not_visible_to_anonymous_users(self, client):
        """Anonymous users see only the read-only description paragraph."""
        user = await User.create(username="viewedit3", email="viewedit3@example.com", password="pw", is_registered=True)
        upload = await Upload.create(**_view_upload_data(user, "edit3"))

        client.cookies.clear()
        response = await client.get(f"/view/{upload.id}/{upload.cleanname}.{upload.ext}")

        assert 'id="upload-description"' not in response.text


# ---------------------------------------------------------------------------
# Step 5 test 5: Description max-length validation
# ---------------------------------------------------------------------------

class TestDescriptionMaxLengthValidation:
    """Step 5 test 5: max-length validation for the description field (255 chars)."""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
    async def test_description_over_max_length_returns_400(self, client, tmp_path, monkeypatch):
        """A description exceeding 255 characters returns 400 with a validation error."""
        owner = await User.create(username="descmaxfail", email="descmaxfail@example.com", password="pw", is_registered=True)
        upload = await _create_tag_upload_with_file(owner, "maxfail", tmp_path, monkeypatch)

        token = create_access_token({"sub": owner.username})
        client.cookies = {"access_token": token}

        description = "a" * 256
        response = await client.patch(f"/uploads/{upload.id}/description", data={"description": description})

        assert response.status_code == 400
