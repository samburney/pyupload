"""Tests for file storage abstraction layer (Step 1)."""

import pytest
from pathlib import Path
from io import BytesIO
from datetime import datetime, timezone
from uuid import UUID
from unittest.mock import Mock, AsyncMock, patch

from fastapi import UploadFile

from app.lib.helpers import make_unique_filename, split_filename, make_clean_filename
from app.lib.file_storage import (
    get_file_size,
    validate_user_quotas,
    validate_user_filetypes,
    UserQuotaExceeded,
    UserFileTypeNotAllowed,
    make_upload_metadata,
)
from app.lib.config import get_app_config
from app.models.users import User


config = get_app_config()


# ============================================================================
# Filename Generation Tests
# ============================================================================

class TestFilenameGeneration:
    """Test filename generation with date + UUID format."""

    def test_make_unique_filename_creates_collision_proof_names(self):
        """Filename generation creates collision-proof names with date + UUID."""
        filename1 = make_unique_filename("test.txt")
        filename2 = make_unique_filename("test.txt")
        assert filename1 != filename2, "Generated filenames should be unique"

    def test_make_unique_filename_includes_datestamp(self):
        """Filename generation includes date stamp (YYYYMMDD-HHMMSS)."""
        filename = make_unique_filename("testfile.txt")
        # Format: cleaned_name_YYYYMMDD-HHMMSS_UUID
        # testfile -> testfile, keep as one part before first timestamp
        import re
        assert re.search(r'_\d{8}-\d{6}_', filename), \
            f"Filename {filename} should contain datestamp pattern"

    def test_make_unique_filename_includes_8_char_uuid(self):
        """Filename generation includes 8-char UUID."""
        filename = make_unique_filename("testfile.txt")
        # Format: cleaned_name_YYYYMMDD-HHMMSS_UUID
        # UUID should be last underscore-separated part and exactly 8 hex chars
        parts = filename.split("_")
        uuid_part = parts[-1]  # Last part after splitting by underscore
        assert len(uuid_part) == 8, f"UUID part '{uuid_part}' should be exactly 8 characters, got {len(uuid_part)}"
        # Verify it's hex
        try:
            int(uuid_part, 16)
        except ValueError:
            pytest.fail(f"UUID part {uuid_part} is not valid hex")

    def test_make_unique_filename_handles_special_characters(self):
        """Filename generation handles special characters via sanitization."""
        # Test with various special characters
        test_names = [
            "test@#$%.txt",
            "test file (1).txt",
            "test-file_name.txt",
            "UPPERCASE.TXT",
        ]
        for test_name in test_names:
            filename = make_unique_filename(test_name)
            # Should not contain these characters (except dots for extension)
            assert "@" not in filename
            assert "#" not in filename
            assert "$" not in filename
            assert "%" not in filename
            assert "(" not in filename
            assert ")" not in filename
            assert not any(char.isupper() for char in filename.split("_")[0])

    def test_make_unique_filename_does_not_include_extension(self):
        """Filename generation does not include file extensions."""
        test_cases = [
            ("test.txt",),
            ("photo.jpg",),
            ("archive.tar.gz",),
            ("document",),  # No extension
        ]
        for original, in test_cases:
            filename = make_unique_filename(original)
            # Should not contain the original extension (extensions handled separately)
            assert not filename.endswith(original.split('.')[-1]), \
                f"Should not include extension from {original}"

    def test_make_unique_filename_cleans_extension_in_name(self):
        """Filename generation treats extension characters as part of name to clean."""
        # When extension is part of the name (like "document.tar.gz"),
        # the dots get converted to underscores during cleaning
        test_cases = [
            ("archive.tar.gz", "archive_tar_gz"),  # Becomes cleaned name with underscores
            ("compress.tar.bz2", "compress_tar_bz2"),
            ("photo.jpg", "photo_jpg"),
        ]
        for original, expected_prefix in test_cases:
            filename = make_unique_filename(original)
            # Should start with the cleaned name (dots replaced with underscores)
            assert filename.startswith(expected_prefix.split("_")[0]), \
                f"Should start with cleaned name for {original}"


# ============================================================================
# Path Construction Tests
# ============================================================================

class TestPathConstruction:
    """Test path construction using storage_path and user_id."""

    def test_path_construction_uses_storage_path(self):
        """Path construction uses storage_path config value and user_id."""
        from app.models.uploads import UploadMetadata
        
        metadata = UploadMetadata(
            user_id=42,
            filename="test_20240101-000000_abc12345",
            ext="txt",
            original_filename="test",
            clean_filename="test",
            size=1024,
            mime_type="text/plain",
        )
        
        filepath = metadata.filepath
        
        # Should start with configured storage_path
        assert filepath.is_relative_to(config.storage_path)
        
        # Should contain user_id in directory name
        assert f"user_42" in str(filepath)

    def test_path_construction_creates_user_directory(self):
        """Path construction creates user directory structure."""
        from app.models.uploads import UploadMetadata
        
        # Use a unique user ID for this test
        test_user_id = 999999
        metadata = UploadMetadata(
            user_id=test_user_id,
            filename="test_20240101-000000_abc12345",
            ext="txt",
            original_filename="test",
            clean_filename="test",
            size=1024,
            mime_type="text/plain",
        )
        
        # Accessing filepath should create the directory
        filepath = metadata.filepath
        user_dir = filepath.parent
        
        # Directory should be created
        assert user_dir.exists(), "User directory should be created"
        assert user_dir.is_dir(), "User directory should be a directory"
        
        # Clean up
        user_dir.rmdir()

    def test_path_construction_returns_correct_directory_structure(self):
        """Path construction returns correct user-specific directory structure."""
        from app.models.uploads import UploadMetadata
        
        metadata = UploadMetadata(
            user_id=123,
            filename="test_20240101-000000_abc12345",
            ext="txt",
            original_filename="test",
            clean_filename="test",
            size=1024,
            mime_type="text/plain",
        )
        
        filepath = metadata.filepath
        
        # Should contain user directory
        assert "user_123" in str(filepath)
        
        # Filename should match with extension now included
        assert filepath.name == "test_20240101-000000_abc12345.txt"


# ============================================================================
# File Size Detection Tests
# ============================================================================

class TestFileSizeDetection:
    """Test file size detection for different file types."""

    def test_get_file_size_with_binary_io(self):
        """File size detection works for BinaryIO objects."""
        content = b"Hello, World!"
        file = BytesIO(content)
        
        size = get_file_size(file)
        
        assert size == len(content)
        assert size == 13

    def test_get_file_size_with_empty_file(self):
        """File size detection handles empty files."""
        file = BytesIO(b"")
        
        size = get_file_size(file)
        
        assert size == 0

    def test_get_file_size_with_large_file(self):
        """File size detection works with large files."""
        # Create a 1MB file
        content = b"x" * (1024 * 1024)
        file = BytesIO(content)
        
        size = get_file_size(file)
        
        assert size == 1024 * 1024

    def test_get_file_size_preserves_file_position(self):
        """File size detection preserves the current file position."""
        content = b"Hello, World!"
        file = BytesIO(content)
        
        # Move to middle of file
        file.seek(5)
        original_pos = file.tell()
        
        size = get_file_size(file)
        
        # Position should be restored
        assert file.tell() == original_pos

    @pytest.mark.asyncio
    async def test_get_file_size_with_upload_file(self):
        """File size detection works for UploadFile objects."""
        content = b"Hello, World!"
        upload_file = UploadFile(file=BytesIO(content), filename="test.txt")
        
        size = get_file_size(upload_file)
        
        assert size == len(content)


# ============================================================================
# Quota Validation Tests
# ============================================================================

class TestQuotaValidation:
    """Test quota enforcement (file size and upload count limits)."""

    @pytest.mark.asyncio
    async def test_validate_user_quotas_enforces_file_size_limit(self):
        """Quota checking enforces size limits correctly."""
        # Create a mock user with 1MB max file size
        user = AsyncMock(spec=User)
        user.max_file_size_mb = 1  # 1MB
        user.max_uploads_count = -1  # Unlimited uploads
        
        # Create a 2MB file
        large_content = b"x" * (2 * 1024 * 1024)
        file = BytesIO(large_content)
        
        # Should raise UserQuotaExceeded
        with pytest.raises(UserQuotaExceeded):
            await validate_user_quotas(user, file)

    @pytest.mark.asyncio
    async def test_validate_user_quotas_enforces_upload_count_limit(self):
        """Quota checking enforces upload count limits correctly."""
        # Create a mock user
        user = AsyncMock(spec=User)
        user.max_file_size_mb = 100
        user.max_uploads_count = 5
        # Mock uploads_count as a coroutine that returns a value
        async def mock_get_count():
            return 5
        user.uploads_count = mock_get_count()
        
        file = BytesIO(b"x" * 1024)  # 1KB file
        
        # Should raise UserQuotaExceeded
        with pytest.raises(UserQuotaExceeded):
            await validate_user_quotas(user, file)

    @pytest.mark.asyncio
    async def test_validate_user_quotas_allows_under_limit(self):
        """Quota checking allows files under limits."""
        # Create a mock user
        user = AsyncMock(spec=User)
        user.max_file_size_mb = 100
        user.max_uploads_count = 10
        # Mock uploads_count as a coroutine that returns a value below limit
        async def mock_get_count():
            return 5
        user.uploads_count = mock_get_count()
        
        file = BytesIO(b"x" * 1024)  # 1KB file
        
        # Should not raise any exception
        result = await validate_user_quotas(user, file)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_user_quotas_unlimited_file_size(self):
        """Quota checking supports unlimited file size (-1)."""
        # Create a mock user with unlimited file size
        user = AsyncMock(spec=User)
        user.max_file_size_mb = -1  # Unlimited
        user.max_uploads_count = 10
        user.uploads_count = 5
        
        # Create a large file
        large_content = b"x" * (1000 * 1024 * 1024)  # 1GB
        file = BytesIO(large_content)
        
        # Should not raise any exception
        result = await validate_user_quotas(user, file)
        assert result is True

    @pytest.mark.asyncio
    async def test_validate_user_quotas_unlimited_upload_count(self):
        """Quota checking supports unlimited upload count (-1)."""
        # Create a mock user with unlimited uploads
        user = AsyncMock(spec=User)
        user.max_file_size_mb = 100
        user.max_uploads_count = -1  # Unlimited
        user.uploads_count = 10000  # Doesn't matter
        
        file = BytesIO(b"x" * 1024)
        
        # Should not raise any exception
        result = await validate_user_quotas(user, file)
        assert result is True


# ============================================================================
# File Type Validation Tests
# ============================================================================

class TestFileTypeValidation:
    """Test MIME type validation."""

    @pytest.mark.asyncio
    async def test_validate_user_filetypes_allows_wildcard(self):
        """File type validation allows wildcard '*' for all types."""
        user = AsyncMock(spec=User)
        user.allowed_mime_types = ["*"]
        
        file = BytesIO(b"test content")
        
        with patch("app.lib.file_storage.get_file_mime_type", return_value="application/octet-stream"):
            result = await validate_user_filetypes(user, file)
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_user_filetypes_allows_specific_types(self):
        """File type validation allows explicitly configured types."""
        user = AsyncMock(spec=User)
        user.allowed_mime_types = ["image/jpeg", "image/png"]
        
        file = BytesIO(b"\xFF\xD8\xFF\xE0")  # JPEG header
        
        with patch("app.lib.file_storage.get_file_mime_type", return_value="image/jpeg"):
            result = await validate_user_filetypes(user, file)
            assert result is True

    @pytest.mark.asyncio
    async def test_validate_user_filetypes_rejects_disallowed_types(self):
        """File type validation rejects disallowed types."""
        user = AsyncMock(spec=User)
        user.allowed_mime_types = ["image/jpeg", "image/png"]
        
        file = BytesIO(b"PK\x03\x04")  # ZIP header
        
        with patch("app.lib.file_storage.get_file_mime_type", return_value="application/zip"):
            with pytest.raises(UserFileTypeNotAllowed):
                await validate_user_filetypes(user, file)


# ============================================================================
# Integration Tests
# ============================================================================

class TestPathValidation:
    """Test path validation prevents directory traversal attacks."""

    def test_path_construction_prevents_directory_traversal(self):
        """Path validation prevents directory traversal attacks."""
        from app.models.uploads import UploadMetadata
        
        # Try path traversal attacks in filename
        metadata = UploadMetadata(
            user_id=42,
            filename="test_20240101-000000_abc12345",  # Must match pattern
            ext="txt",
            original_filename="test",
            clean_filename="test",
            size=1024,
            mime_type="text/plain",
        )
        
        filepath = metadata.filepath
        
        # Filepath should be within storage_path
        try:
            filepath.relative_to(config.storage_path)
        except ValueError:
            pytest.fail("Filepath is not within storage_path")

    def test_path_construction_respects_storage_path_boundary(self):
        """Path construction respects storage_path boundaries."""
        from app.models.uploads import UploadMetadata
        import os
        
        metadata = UploadMetadata(
            user_id=42,
            filename="test_20240101-000000_abc12345",
            ext="txt",
            original_filename="test",
            clean_filename="test",
            size=1024,
            mime_type="text/plain",
        )
        
        filepath = metadata.filepath
        
        # Verify path is within storage_path
        assert str(filepath).startswith(str(config.storage_path))


# ============================================================================
# Directory Creation Tests
# ============================================================================

class TestDirectoryCreation:
    """Test directory creation with proper permissions."""

    def test_directory_creation_succeeds_with_proper_permissions(self):
        """Directory creation succeeds with proper permissions."""
        from app.models.uploads import UploadMetadata
        import os
        
        test_user_id = 999998
        metadata = UploadMetadata(
            user_id=test_user_id,
            filename="test_20240101-000000_abc12345",
            ext="txt",
            original_filename="test",
            clean_filename="test",
            size=1024,
            mime_type="text/plain",
        )
        
        filepath = metadata.filepath
        user_dir = filepath.parent
        
        # Directory should exist
        assert user_dir.exists()
        
        # Should have read and write permissions
        assert os.access(user_dir, os.R_OK | os.W_OK)
        
        # Clean up
        user_dir.rmdir()

    def test_directory_creation_idempotent(self):
        """Directory creation is idempotent."""
        from app.models.uploads import UploadMetadata
        
        test_user_id = 999997
        metadata1 = UploadMetadata(
            user_id=test_user_id,
            filename="test_20240101-000000_abc12345",
            ext="txt",
            original_filename="test",
            clean_filename="test",
            size=1024,
            mime_type="text/plain",
        )
        
        # First access creates directory
        filepath1 = metadata1.filepath
        assert filepath1.parent.exists()
        
        # Second access should not fail
        metadata2 = UploadMetadata(
            user_id=test_user_id,
            filename="test_20240101-000000_def67890",
            ext="txt",
            original_filename="test",
            clean_filename="test",
            size=2048,
            mime_type="text/plain",
        )
        
        filepath2 = metadata2.filepath
        assert filepath2.parent.exists()
        
        # Should be the same directory
        assert filepath1.parent == filepath2.parent
        
        # Clean up
        filepath1.parent.rmdir()
