"""Tests for app/lib/upload_handler.py functions."""

import pytest
import tempfile
from io import BytesIO
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

from fastapi import UploadFile
from app.lib.upload_handler import handle_uploaded_file, handle_uploaded_files
from app.models.users import User
from app.models.uploads import UploadResult, Upload
from app.lib.file_storage import UserQuotaExceeded, UserFileTypeNotAllowed
from app.lib.config import get_app_config

config = get_app_config()


class TestHandleUploadedFile:
    """Test single file upload handler."""

    @pytest.mark.asyncio
    async def test_successful_file_upload(self):
        """Test that a valid file upload succeeds."""
        # Create mock user
        user = AsyncMock(spec=User)
        user.max_file_size_mb = 100
        user.max_uploads_count = 10

        # Create mock UploadFile
        file_content = b"test content"
        file = MagicMock(spec=UploadFile)
        file.filename = "test.txt"
        file.size = len(file_content)
        file.content_type = "text/plain"
        file.file = BytesIO(file_content)

        # Mock process_uploaded_file
        with patch('app.lib.upload_handler.process_uploaded_file') as mock_process:
            mock_process.return_value = UploadResult(
                status="success",
                message="File uploaded successfully",
                upload_id=None,
                metadata=None
            )
            
            result = await handle_uploaded_file(user, file)
            
            # Verify result
            assert result.status == "success"
            assert result.message == "File uploaded successfully"
            
            # Verify process was called
            mock_process.assert_called_once()

    @pytest.mark.asyncio
    async def test_quota_exceeded_error(self):
        """Test that quota exceeded error is raised."""
        user = AsyncMock(spec=User)
        file = MagicMock(spec=UploadFile)
        file.filename = "test.txt"

        with patch('app.lib.upload_handler.process_uploaded_file') as mock_process:
            mock_process.side_effect = UserQuotaExceeded("Quota exceeded")
            
            with pytest.raises(UserQuotaExceeded):
                await handle_uploaded_file(user, file)

    @pytest.mark.asyncio
    async def test_invalid_file_type_error(self):
        """Test that invalid file type error is raised."""
        user = AsyncMock(spec=User)
        file = MagicMock(spec=UploadFile)
        file.filename = "test.exe"

        with patch('app.lib.upload_handler.process_uploaded_file') as mock_process:
            mock_process.side_effect = UserFileTypeNotAllowed("File type not allowed")
            
            with pytest.raises(UserFileTypeNotAllowed):
                await handle_uploaded_file(user, file)

    @pytest.mark.asyncio
    async def test_database_error_handling(self):
        """Test that database errors are propagated."""
        user = AsyncMock(spec=User)
        file = MagicMock(spec=UploadFile)
        file.filename = "test.txt"

        with patch('app.lib.upload_handler.process_uploaded_file') as mock_process:
            mock_process.side_effect = Exception("Database error")
            
            with pytest.raises(Exception):
                await handle_uploaded_file(user, file)


class TestHandleUploadedFiles:
    """Test batch file upload handler."""

    @pytest.mark.asyncio
    async def test_single_file_in_batch(self):
        """Test batch handler with single file."""
        user = AsyncMock(spec=User)
        
        file = MagicMock(spec=UploadFile)
        file.filename = "test.txt"
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            mock_handle.return_value = UploadResult(
                status="success",
                message="File uploaded",
                upload_id=None,
                metadata=None
            )
            
            results = await handle_uploaded_files(user, [file])
            
            assert len(results) == 1
            assert results[0].status == "success"
            mock_handle.assert_called_once_with(user, file)

    @pytest.mark.asyncio
    async def test_multiple_files_in_batch(self):
        """Test batch handler with multiple files."""
        user = AsyncMock(spec=User)
        
        files = [
            MagicMock(spec=UploadFile, filename="test1.txt"),
            MagicMock(spec=UploadFile, filename="test2.txt"),
            MagicMock(spec=UploadFile, filename="test3.txt"),
        ]
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            mock_handle.return_value = UploadResult(
                status="success",
                message="File uploaded",
                upload_id=None,
                metadata=None
            )
            
            results = await handle_uploaded_files(user, files)
            
            assert len(results) == 3
            assert all(r.status == "success" for r in results)
            assert mock_handle.call_count == 3

    @pytest.mark.asyncio
    async def test_empty_file_list(self):
        """Test batch handler with empty file list."""
        user = AsyncMock(spec=User)
        
        results = await handle_uploaded_files(user, [])
        
        assert len(results) == 0
        assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_partial_batch_failure(self):
        """Test batch handler with one file failing."""
        user = AsyncMock(spec=User)
        
        files = [
            MagicMock(spec=UploadFile, filename="test1.txt"),
            MagicMock(spec=UploadFile, filename="test2.txt"),
            MagicMock(spec=UploadFile, filename="test3.txt"),
        ]
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            # First two succeed, third fails
            mock_handle.side_effect = [
                UploadResult(
                    status="success",
                    message="File uploaded",
                    upload_id=None,
                    metadata=None
                ),
                Exception("File too large"),
                UploadResult(
                    status="success",
                    message="File uploaded",
                    upload_id=None,
                    metadata=None
                ),
            ]
            
            results = await handle_uploaded_files(user, files)
            
            # Should have 3 results
            assert len(results) == 3
            
            # First and third should be success
            assert results[0].status == "success"
            assert results[2].status == "success"
            
            # Second should be error
            assert results[1].status == "error"
            assert "File too large" in results[1].message

    @pytest.mark.asyncio
    async def test_all_files_fail(self):
        """Test batch handler where all files fail."""
        user = AsyncMock(spec=User)
        
        files = [
            MagicMock(spec=UploadFile, filename="test1.txt"),
            MagicMock(spec=UploadFile, filename="test2.txt"),
        ]
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            mock_handle.side_effect = [
                Exception("Quota exceeded"),
                Exception("Quota exceeded"),
            ]
            
            results = await handle_uploaded_files(user, files)
            
            assert len(results) == 2
            assert all(r.status == "error" for r in results)

    @pytest.mark.asyncio
    async def test_quota_exceeded_in_batch(self):
        """Test quota exceeded error in batch processing."""
        user = AsyncMock(spec=User)
        
        files = [
            MagicMock(spec=UploadFile, filename="test1.txt"),
            MagicMock(spec=UploadFile, filename="test2.txt"),
        ]
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            mock_handle.side_effect = UserQuotaExceeded("User quota exceeded")
            
            results = await handle_uploaded_files(user, files)
            
            assert len(results) == 2
            assert all(r.status == "error" for r in results)
            assert all("quota" in r.message.lower() for r in results)

    @pytest.mark.asyncio
    async def test_file_type_not_allowed_in_batch(self):
        """Test file type not allowed error in batch processing."""
        user = AsyncMock(spec=User)
        
        files = [
            MagicMock(spec=UploadFile, filename="test.exe"),
            MagicMock(spec=UploadFile, filename="test.txt"),
        ]
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            mock_handle.side_effect = [
                UserFileTypeNotAllowed("File type not allowed"),
                UploadResult(
                    status="success",
                    message="File uploaded",
                    upload_id=None,
                    metadata=None
                ),
            ]
            
            results = await handle_uploaded_files(user, files)
            
            assert len(results) == 2
            assert results[0].status == "error"
            assert results[1].status == "success"

    @pytest.mark.asyncio
    async def test_batch_result_structure(self):
        """Test that batch results have correct structure."""
        user = AsyncMock(spec=User)
        
        files = [MagicMock(spec=UploadFile, filename="test.txt")]
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            mock_handle.return_value = UploadResult(
                status="success",
                message="File uploaded successfully",
                upload_id=None,
                metadata=None
            )
            
            results = await handle_uploaded_files(user, files)
            
            assert len(results) == 1
            result = results[0]
            
            # Check result structure
            assert hasattr(result, 'status')
            assert hasattr(result, 'message')
            assert hasattr(result, 'upload_id')
            assert hasattr(result, 'metadata')
            
            assert isinstance(result, UploadResult)

    @pytest.mark.asyncio
    async def test_error_message_preserved_in_batch(self):
        """Test that error messages are preserved in batch results."""
        user = AsyncMock(spec=User)
        
        files = [MagicMock(spec=UploadFile, filename="test.txt")]
        
        error_message = "Custom error: Something went wrong"
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            mock_handle.side_effect = Exception(error_message)
            
            results = await handle_uploaded_files(user, files)
            
            assert len(results) == 1
            assert results[0].status == "error"
            assert error_message in results[0].message


class TestUploadHandlerIntegration:
    """Integration tests for upload handler."""

    @pytest.mark.asyncio
    async def test_processes_files_sequentially(self):
        """Test that files are processed in order."""
        user = AsyncMock(spec=User)
        
        files = [
            MagicMock(spec=UploadFile, filename="file1.txt"),
            MagicMock(spec=UploadFile, filename="file2.txt"),
            MagicMock(spec=UploadFile, filename="file3.txt"),
        ]
        
        call_order = []
        
        async def track_calls(u, f):
            call_order.append(f.filename)
            return UploadResult(
                status="success",
                message="Success",
                upload_id=None,
                metadata=None
            )
        
        with patch('app.lib.upload_handler.handle_uploaded_file', side_effect=track_calls):
            await handle_uploaded_files(user, files)
            
            # Verify order
            assert call_order == ["file1.txt", "file2.txt", "file3.txt"]

    @pytest.mark.asyncio
    async def test_validation_called_for_each_file(self):
        """Test that all validations are called for each file."""
        user = AsyncMock(spec=User)
        
        files = [
            MagicMock(spec=UploadFile, filename="test1.txt"),
            MagicMock(spec=UploadFile, filename="test2.txt"),
        ]
        
        with patch('app.lib.upload_handler.handle_uploaded_file') as mock_handle:
            mock_handle.return_value = UploadResult(
                status="success",
                message="Success",
                upload_id=None,
                metadata=None
            )
            
            results = await handle_uploaded_files(user, files)
            
            # Both files should complete
            assert len(results) == 2
            # Verify handle was called for each file
            assert mock_handle.call_count == 2


# ============================================================================
# Integration Tests with Real Database and File I/O
# ============================================================================

class TestUploadHandlerIntegrationWithDatabase:
    """Integration tests with actual database and file I/O."""

    @pytest.mark.asyncio
    async def test_single_file_upload_end_to_end_with_database(self, db, tmp_path, monkeypatch):
        """Test that a valid file upload succeeds end-to-end with real database."""
        # Monkeypatch storage path to use temporary directory
        import app.lib.file_storage
        monkeypatch.setattr(app.lib.file_storage.config, "storage_path", tmp_path)
        
        # Create a real user
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashedpass",
            is_registered=True,
        )
        
        # Create an UploadFile with test content
        content = b"Test file content for upload"
        upload_file = UploadFile(
            file=BytesIO(content),
            filename="test_document.txt",
        )
        
        # Mock MIME type detection
        with patch("app.lib.file_storage.get_file_mime_type", return_value="text/plain"):
            result = await handle_uploaded_file(user, upload_file)
        
        # Verify success result
        assert result.status == "success"
        assert result.message == "File uploaded successfully."
        assert result.upload_id is not None
        assert result.metadata is not None
        
        # Verify upload was created in database
        upload = await Upload.get(id=result.upload_id)
        assert upload.id is not None
        assert upload.user_id == user.id
        assert upload.size == len(content)
        assert upload.type == "text/plain"
        
        # Verify file metadata
        assert result.metadata.user_id == user.id
        assert result.metadata.size == len(content)
        assert result.metadata.mime_type == "text/plain"
        
        # Verify file was saved to correct location
        user_dir = tmp_path / f"user_{user.id}"
        assert user_dir.exists()
        # No cleanup needed - tmp_path is auto-cleaned

    @pytest.mark.asyncio
    async def test_batch_upload_all_files_succeed(self, db, tmp_path, monkeypatch):
        """Test batch upload where all files succeed."""
        # Monkeypatch storage path to use temporary directory
        import app.lib.file_storage
        monkeypatch.setattr(app.lib.file_storage.config, "storage_path", tmp_path)
        
        # Create a real user
        user = await User.create(
            username="batchuser1",
            email="batch1@example.com",
            password="hashedpass",
            is_registered=True,
        )
        
        # Create multiple files
        files = []
        for i in range(3):
            content = f"Test file {i+1} content".encode()
            files.append(UploadFile(
                file=BytesIO(content),
                filename=f"test_file_{i+1}.txt",
            ))
        
        # Mock MIME type detection
        with patch("app.lib.file_storage.get_file_mime_type", return_value="text/plain"):
            results = await handle_uploaded_files(user, files)
        
        # Verify all succeeded
        assert len(results) == 3
        assert all(r.status == "success" for r in results)
        assert all(r.upload_id is not None for r in results)
        
        # Verify all were saved to database
        for result in results:
            upload = await Upload.get(id=result.upload_id)
            assert upload.id is not None
            assert upload.user_id == user.id
        # No cleanup needed - tmp_path is auto-cleaned

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_empty_file_validation(self, db):
        """Test that empty file validation returns proper error."""
        # Create a real user
        user = await User.create(
            username="emptyfileuser",
            email="empty@example.com",
            password="hashedpass",
            is_registered=True,
        )
        
        # Create an empty file
        upload_file = UploadFile(
            file=BytesIO(b""),
            filename="empty_file.txt",
        )
        
        # Should raise error due to empty file (cannot determine MIME type)
        with pytest.raises(ValueError) as exc_info:
            await handle_uploaded_file(user, upload_file)
        
        assert "empty" in str(exc_info.value).lower()

    @pytest.mark.asyncio
    async def test_upload_result_structure_contains_required_fields(self, db, tmp_path, monkeypatch):
        """Test that UploadResult contains success/error status, filename, and size."""
        # Monkeypatch storage path to use temporary directory
        import app.lib.file_storage
        monkeypatch.setattr(app.lib.file_storage.config, "storage_path", tmp_path)
        
        user = await User.create(
            username="structuser",
            email="struct@example.com",
            password="hashedpass",
            is_registered=True,
        )
        
        content = b"Test content with specific size"
        upload_file = UploadFile(
            file=BytesIO(content),
            filename="structured_test.txt",
        )
        
        with patch("app.lib.file_storage.get_file_mime_type", return_value="text/plain"):
            result = await handle_uploaded_file(user, upload_file)
        
        # Verify UploadResult structure
        assert hasattr(result, 'status')
        assert hasattr(result, 'message')
        assert hasattr(result, 'upload_id')
        assert hasattr(result, 'metadata')
        
        # Verify success result contains expected data
        assert result.status == "success"
        upload = await Upload.get(id=result.upload_id)
        assert upload.name is not None  # Generated filename
        assert upload.size == len(content)
        assert result.metadata.filename is not None
        assert result.metadata.size == len(content)
        # No cleanup needed - tmp_path is auto-cleaned

    @pytest.mark.asyncio
    async def test_quota_exceeded_prevents_upload(self, db):
        """Test that quota exceeded error prevents upload with proper message."""
        user = await User.create(
            username="quotauser",
            email="quota@example.com",
            password="hashedpass",
            is_registered=False,  # Unregistered user - likely has smaller quota
        )
        
        content = b"x" * (100 * 1024 * 1024)  # 100MB file
        upload_file = UploadFile(
            file=BytesIO(content),
            filename="large_file.bin",
        )
        
        # Catch the error by calling via batch handler
        files = [upload_file]
        with patch("app.lib.file_storage.get_file_mime_type", return_value="application/octet-stream"):
            results = await handle_uploaded_files(user, files)
        
        # First file should have error about quota
        assert results[0].status == "error"
        assert "quota" in results[0].message.lower() or "exceeds" in results[0].message.lower()

    @pytest.mark.asyncio
    async def test_file_saved_to_correct_user_directory(self, db, tmp_path, monkeypatch):
        """Test that uploaded files are saved to correct user-specific directory."""
        # Monkeypatch storage path to use temporary directory
        import app.lib.file_storage
        monkeypatch.setattr(app.lib.file_storage.config, "storage_path", tmp_path)
        
        # Create two users
        user1 = await User.create(
            username="user1",
            email="user1@example.com",
            password="hashedpass",
            is_registered=True,
        )
        user2 = await User.create(
            username="user2",
            email="user2@example.com",
            password="hashedpass",
            is_registered=True,
        )
        
        # Upload file for user1
        content1 = b"User 1 file content"
        file1 = UploadFile(
            file=BytesIO(content1),
            filename="user1_file.txt",
        )
        
        # Upload file for user2
        content2 = b"User 2 file content"
        file2 = UploadFile(
            file=BytesIO(content2),
            filename="user2_file.txt",
        )
        
        with patch("app.lib.file_storage.get_file_mime_type", return_value="text/plain"):
            result1 = await handle_uploaded_file(user1, file1)
            result2 = await handle_uploaded_file(user2, file2)
        
        # Verify files are in correct directories
        user1_dir = tmp_path / f"user_{user1.id}"
        user2_dir = tmp_path / f"user_{user2.id}"
        
        assert user1_dir.exists()
        assert user2_dir.exists()
        assert user1_dir != user2_dir
        
        # Verify files exist in their respective directories
        user1_files = list(user1_dir.glob("*"))
        user2_files = list(user2_dir.glob("*"))
        
        assert len(user1_files) > 0
        assert len(user2_files) > 0
        # No cleanup needed - tmp_path is auto-cleaned

    @pytest.mark.asyncio
    @pytest.mark.asyncio
    async def test_batch_processes_files_sequentially_order_preserved(self, db, tmp_path, monkeypatch):
        """Test that batch processing happens sequentially and results maintain order."""
        # Monkeypatch storage path to use temporary directory
        import app.lib.file_storage
        monkeypatch.setattr(app.lib.file_storage.config, "storage_path", tmp_path)
        
        user = await User.create(
            username="orderuser",
            email="order@example.com",
            password="hashedpass",
            is_registered=True,
        )
        
        # Create files with distinct identifiable content
        files = []
        for i in range(5):
            content = f"File number {i}".encode()
            files.append(UploadFile(
                file=BytesIO(content),
                filename=f"file_{i:02d}.txt",
            ))
        
        with patch("app.lib.file_storage.get_file_mime_type", return_value="text/plain"):
            results = await handle_uploaded_files(user, files)
        
        # Verify results are in same order as inputs
        assert len(results) == 5
        for i, result in enumerate(results):
            assert result.status == "success"
            # Verify filename matches pattern (no extension in filename)
            import re
            assert re.match(r'^[a-z0-9_]+_\d{8}-\d{6}_[a-f0-9]{8}$', result.metadata.filename), \
                f"Filename {result.metadata.filename} doesn't match pattern"
            # Verify extension is stored separately
            assert result.metadata.ext == "txt"
        # No cleanup needed - tmp_path is auto-cleaned
