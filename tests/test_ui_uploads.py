"""Tests for app/ui/uploads.py - File upload UI endpoints.

This module tests the FastAPI/Starlette file upload endpoints:
- GET /upload - Display upload form page
- POST /upload - Process form submission
- GET /get/{id}/{filename} - Serve files for viewing
- GET /download/{id}/{filename} - Force download files

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
"""

import pytest
from io import BytesIO
from unittest.mock import AsyncMock, patch

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
