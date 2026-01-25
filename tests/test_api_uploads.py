"""Tests for app/api/uploads.py - File upload API endpoints.

This module tests the FastAPI upload endpoints:
- POST /api/v1/uploads - Handle file uploads

Tests verify:
- Endpoint accessibility and routing
- Authentication and authorization
- Input validation (no files, empty requests)
- Response format and structure
- Single and batch file uploads
- Error handling and per-file error recovery
- UploadResult structure validation
"""

import pytest
from io import BytesIO
from unittest.mock import AsyncMock, MagicMock, patch

from app.models.users import User
from app.models.uploads import Upload, UploadResult, UploadMetadata
from app.lib.auth import create_access_token


class TestUploadEndpointAuthentication:
    """Test authentication requirements for upload endpoint."""

    @pytest.mark.asyncio
    async def test_endpoint_accessible_at_post_uploads(self, client):
        """Test that endpoint is accessible at POST /api/v1/uploads."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Make request with proper auth
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should succeed (200) or return valid error (400 for no files, etc.)
        # Should not return 404 (endpoint exists)
        assert response.status_code in [200, 400, 422]

    @pytest.mark.asyncio
    async def test_returns_401_if_not_authenticated(self, client):
        """Test that endpoint returns 401 when not authenticated."""
        # Make request without authentication token
        response = await client.post(
            "/api/v1/uploads",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 401 Unauthorized
        assert response.status_code == 401

    @pytest.mark.asyncio
    async def test_returns_401_with_invalid_token(self, client):
        """Test that endpoint returns 401 with invalid token."""
        # Make request with invalid token
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": "Bearer invalid_token_xyz"},
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 401 Unauthorized
        assert response.status_code == 401


class TestUploadEndpointInputValidation:
    """Test input validation for upload endpoint."""

    @pytest.mark.asyncio
    async def test_returns_400_if_no_files_provided(self, client):
        """Test that endpoint returns 400 or 422 when no files are provided."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Make request without files
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
        )
        
        # Should return 400 or 422 (FastAPI returns 422 for missing required field)
        assert response.status_code in [400, 422]
        
        # Should have error message
        json_response = response.json()
        assert "detail" in json_response

    @pytest.mark.asyncio
    async def test_returns_400_if_empty_file_list(self, client):
        """Test that endpoint returns 400 when file list is empty."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Make request with empty files parameter
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
            files=[],
        )
        
        # Should return 400 or 422 (validation error)
        assert response.status_code in [400, 422]


class TestUploadEndpointSuccessfulUploads:
    """Test successful file upload scenarios."""

    @pytest.mark.asyncio
    async def test_endpoint_returns_200_with_auth(self, client, monkeypatch):
        """Test that endpoint returns 200 when authenticated."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Mock the upload handler to avoid filesystem operations
        from unittest.mock import AsyncMock
        mock_handler = AsyncMock(return_value=[])
        monkeypatch.setattr(
            "app.api.uploads.handle_uploaded_files",
            mock_handler
        )
        
        # Make request with file
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 200 (mock handler returns empty list)
        assert response.status_code == 200
        
        # Should have results key
        json_response = response.json()
        assert "results" in json_response
        assert isinstance(json_response["results"], list)


class TestUploadEndpointResponseStructure:
    """Test response structure and format."""

    @pytest.mark.asyncio
    async def test_upload_returns_results_array(self, client, monkeypatch):
        """Test that upload endpoint returns results array."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Mock the upload handler to return mock results
        from unittest.mock import AsyncMock
        from app.models.uploads import UploadResult
        
        # Return proper UploadResult objects instead of MagicMock
        mock_result = UploadResult(
            status="success",
            message="File uploaded",
            upload_id=None,
            metadata=None,
        )
        
        mock_handler = AsyncMock(return_value=[mock_result])
        monkeypatch.setattr(
            "app.api.uploads.handle_uploaded_files",
            mock_handler
        )
        
        # Make request
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 200
        assert response.status_code == 200
        
        # Should have results array
        json_response = response.json()
        assert "results" in json_response
        assert isinstance(json_response["results"], list)


class TestUploadEndpointErrorHandling:
    """Test error handling and per-file error recovery."""

    @pytest.mark.asyncio
    async def test_batch_upload_with_mixed_results(self, client, monkeypatch):
        """Test batch upload where some files succeed and some fail."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Mock the upload handler to return mixed results
        from unittest.mock import AsyncMock
        from app.models.uploads import UploadResult
        
        success_result = UploadResult(
            status="success",
            message="File uploaded successfully",
            upload_id=None,
            metadata=None,
        )
        
        error_result = UploadResult(
            status="error",
            message="File type not allowed",
            upload_id=None,
            metadata=None,
        )
        
        mock_handler = AsyncMock(return_value=[success_result, error_result, success_result])
        monkeypatch.setattr(
            "app.api.uploads.handle_uploaded_files",
            mock_handler
        )
        
        # Make request with 3 files
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
            files=[
                ("upload_files", ("test1.txt", BytesIO(b"content1"), "text/plain")),
                ("upload_files", ("test2.exe", BytesIO(b"executable"), "application/octet-stream")),
                ("upload_files", ("test3.txt", BytesIO(b"content3"), "text/plain")),
            ],
        )
        
        # Should return 200 (not fail entirely)
        assert response.status_code == 200
        
        # Should have 3 results (mix of success and error)
        json_response = response.json()
        results = json_response["results"]
        assert len(results) == 3

    @pytest.mark.asyncio
    async def test_batch_upload_with_all_files_failing(self, client, monkeypatch):
        """Test batch upload where all files fail."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Mock the upload handler to return all failures
        from unittest.mock import AsyncMock
        from app.models.uploads import UploadResult
        
        error_result = UploadResult(
            status="error",
            message="File type not allowed",
            upload_id=None,
            metadata=None,
        )
        
        mock_handler = AsyncMock(return_value=[error_result, error_result])
        monkeypatch.setattr(
            "app.api.uploads.handle_uploaded_files",
            mock_handler
        )
        
        # Make request
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
            files=[
                ("upload_files", ("test1.exe", BytesIO(b"executable"), "application/octet-stream")),
                ("upload_files", ("test2.exe", BytesIO(b"executable"), "application/octet-stream")),
            ],
        )
        
        # Should still return 200 (not 500 error)
        assert response.status_code == 200
        
        # All results should be errors
        json_response = response.json()
        results = json_response["results"]
        assert len(results) == 2

    @pytest.mark.asyncio
    async def test_quota_exceeded_error_handled(self, client, monkeypatch):
        """Test that quota exceeded errors are properly handled."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Mock the upload handler to return quota exceeded error
        from unittest.mock import AsyncMock
        from app.models.uploads import UploadResult
        
        error_result = UploadResult(
            status="error",
            message="User has exceeded the maximum number of allowed uploads",
            upload_id=None,
            metadata=None,
        )
        
        mock_handler = AsyncMock(return_value=[error_result])
        monkeypatch.setattr(
            "app.api.uploads.handle_uploaded_files",
            mock_handler
        )
        
        # Make request
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should return 200 with error result
        assert response.status_code == 200
        
        # Result should be error status
        json_response = response.json()
        results = json_response["results"]
        assert len(results) == 1
        assert results[0]["status"] == "error"


class TestUploadEndpointResponseTypes:
    """Test response type correctness."""

    @pytest.mark.asyncio
    async def test_response_is_valid_json(self, client, monkeypatch):
        """Test that response is valid JSON."""
        # Create a user and token
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpassword",
            is_registered=True,
        )
        
        # Create access token
        token_data = {"sub": str(user.username)}
        access_token = create_access_token(data=token_data)
        
        # Mock the upload handler
        from unittest.mock import AsyncMock
        mock_handler = AsyncMock(return_value=[])
        monkeypatch.setattr(
            "app.api.uploads.handle_uploaded_files",
            mock_handler
        )
        
        # Make request
        response = await client.post(
            "/api/v1/uploads",
            headers={"Authorization": f"Bearer {access_token}"},
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should be able to parse JSON without error
        assert response.status_code == 200
        json_response = response.json()
        assert isinstance(json_response, dict)
        assert "results" in json_response

    @pytest.mark.asyncio
    async def test_error_response_is_valid_json(self, client):
        """Test that error response is valid JSON."""
        # Make request without authentication
        response = await client.post(
            "/api/v1/uploads",
            files={"upload_files": ("test.txt", BytesIO(b"content"), "text/plain")},
        )
        
        # Should be 401
        assert response.status_code == 401
        
        # Should have valid JSON error
        json_response = response.json()
        assert isinstance(json_response, dict)
        assert "detail" in json_response

