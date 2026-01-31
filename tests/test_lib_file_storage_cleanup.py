"""Tests for cleanup_orphaned_files function in file_storage module."""

import pytest
from pathlib import Path
from datetime import datetime, timedelta
from unittest.mock import patch, AsyncMock
import time

from app.lib.file_storage import cleanup_orphaned_files
from app.lib.config import get_app_config
from app.models.uploads import Upload
from app.models.users import User


config = get_app_config()


@pytest.mark.asyncio
class TestCleanupOrphanedFiles:
    """Test orphaned file cleanup functionality."""

    async def test_cleanup_ignores_dotfiles(self, tmp_path):
        """Test that dotfiles are ignored during cleanup."""
        # Create user directory
        user_dir = tmp_path / "data" / "files" / "user_1"
        user_dir.mkdir(parents=True)
        
        # Create a dotfile
        dotfile = user_dir / ".DS_Store"
        dotfile.write_text("system file")
        
        # Patch config to use tmp_path
        with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
            with patch.object(config, 'storage_orphaned_max_age_hours', 0):
                orphans_found = await cleanup_orphaned_files()
        
        # Dotfile should not be deleted
        assert dotfile.exists()
        assert orphans_found == 0

    async def test_cleanup_ignores_recent_files(self, tmp_path):
        """Test that recently created files are not deleted."""
        # Create user directory
        user_dir = tmp_path / "data" / "files" / "user_1"
        user_dir.mkdir(parents=True)
        
        # Create a recent file
        recent_file = user_dir / "test_20240101-120000_abc12345.txt"
        recent_file.write_text("recent content")
        
        # Patch config to use tmp_path with 24 hour retention
        with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
            with patch.object(config, 'storage_orphaned_max_age_hours', 24):
                orphans_found = await cleanup_orphaned_files()
        
        # Recent file should not be deleted
        assert recent_file.exists()
        assert orphans_found == 0

    async def test_cleanup_deletes_old_orphaned_files(self, tmp_path):
        """Test that old orphaned files are deleted."""
        # Create user directory
        user_dir = tmp_path / "data" / "files" / "user_1"
        user_dir.mkdir(parents=True)
        
        # Create an old file
        old_file = user_dir / "test_20240101-120000_abc12345.txt"
        old_file.write_text("old content")
        
        # Make the file old by modifying its mtime
        old_time = time.time() - (25 * 3600)  # 25 hours ago
        Path.touch(old_file)
        import os
        os.utime(old_file, (old_time, old_time))
        
        # Mock Upload.get_or_none to return None (no DB record)
        async def mock_get_or_none(**kwargs):
            return None
        
        with patch.object(Upload, 'get_or_none', side_effect=mock_get_or_none):
            with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
                with patch.object(config, 'storage_orphaned_max_age_hours', 24):
                    orphans_found = await cleanup_orphaned_files()
        
        # Old orphaned file should be deleted
        assert not old_file.exists()
        assert orphans_found == 1

    async def test_cleanup_preserves_files_with_db_records(self, tmp_path):
        """Test that files with database records are preserved."""
        # Create user directory
        user_dir = tmp_path / "data" / "files" / "user_1"
        user_dir.mkdir(parents=True)
        
        # Create an old file
        old_file = user_dir / "test_20240101-120000_abc12345.txt"
        old_file.write_text("old content")
        
        # Make the file old
        old_time = time.time() - (25 * 3600)
        import os
        os.utime(old_file, (old_time, old_time))
        
        # Mock Upload.get_or_none to return a mock upload (DB record exists)
        mock_upload = AsyncMock(spec=Upload)
        
        async def mock_get_or_none(**kwargs):
            return mock_upload
        
        with patch.object(Upload, 'get_or_none', side_effect=mock_get_or_none):
            with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
                with patch.object(config, 'storage_orphaned_max_age_hours', 24):
                    orphans_found = await cleanup_orphaned_files()
        
        # File should be preserved
        assert old_file.exists()
        assert orphans_found == 0

    async def test_cleanup_handles_multipart_extensions(self, tmp_path):
        """Test that files with multipart extensions are handled correctly."""
        # Create user directory
        user_dir = tmp_path / "data" / "files" / "user_1"
        user_dir.mkdir(parents=True)
        
        # Create an old file with multipart extension
        old_file = user_dir / "archive_20240101-120000_abc12345.tar.gz"
        old_file.write_text("archive content")
        
        # Make the file old
        old_time = time.time() - (25 * 3600)
        import os
        os.utime(old_file, (old_time, old_time))
        
        # Mock Upload.get_or_none to check the query parameters
        async def mock_get_or_none(**kwargs):
            # Should query with name="archive_20240101-120000_abc12345" and ext="tar.gz"
            assert kwargs['name'] == "archive_20240101-120000_abc12345"
            assert kwargs['ext'] == "tar.gz"
            return None  # No record found, so it's orphaned
        
        with patch.object(Upload, 'get_or_none', side_effect=mock_get_or_none):
            with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
                with patch.object(config, 'storage_orphaned_max_age_hours', 24):
                    orphans_found = await cleanup_orphaned_files()
        
        # File should be deleted
        assert not old_file.exists()
        assert orphans_found == 1

    async def test_cleanup_handles_no_extension_files(self, tmp_path):
        """Test that files without extensions are handled correctly."""
        # Create user directory
        user_dir = tmp_path / "data" / "files" / "user_1"
        user_dir.mkdir(parents=True)
        
        # Create an old file without extension
        old_file = user_dir / "readme_20240101-120000_abc12345"
        old_file.write_text("readme content")
        
        # Make the file old
        old_time = time.time() - (25 * 3600)
        import os
        os.utime(old_file, (old_time, old_time))
        
        # Mock Upload.get_or_none to check the query parameters
        async def mock_get_or_none(**kwargs):
            assert kwargs['name'] == "readme_20240101-120000_abc12345"
            assert kwargs['ext'] == ""
            return None
        
        with patch.object(Upload, 'get_or_none', side_effect=mock_get_or_none):
            with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
                with patch.object(config, 'storage_orphaned_max_age_hours', 24):
                    orphans_found = await cleanup_orphaned_files()
        
        # File should be deleted
        assert not old_file.exists()
        assert orphans_found == 1

    async def test_cleanup_handles_multiple_users(self, tmp_path):
        """Test that cleanup works across multiple user directories."""
        # Create multiple user directories
        user1_dir = tmp_path / "data" / "files" / "user_1"
        user2_dir = tmp_path / "data" / "files" / "user_2"
        user1_dir.mkdir(parents=True)
        user2_dir.mkdir(parents=True)
        
        # Create old files in both directories
        old_file1 = user1_dir / "test1_20240101-120000_abc12345.txt"
        old_file2 = user2_dir / "test2_20240101-120000_def67890.txt"
        old_file1.write_text("content1")
        old_file2.write_text("content2")
        
        # Make files old
        old_time = time.time() - (25 * 3600)
        import os
        os.utime(old_file1, (old_time, old_time))
        os.utime(old_file2, (old_time, old_time))
        
        # Mock Upload.get_or_none to return None (no DB records)
        async def mock_get_or_none(**kwargs):
            return None
        
        with patch.object(Upload, 'get_or_none', side_effect=mock_get_or_none):
            with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
                with patch.object(config, 'storage_orphaned_max_age_hours', 24):
                    orphans_found = await cleanup_orphaned_files()
        
        # Both files should be deleted
        assert not old_file1.exists()
        assert not old_file2.exists()
        assert orphans_found == 2

    async def test_cleanup_handles_deletion_errors_gracefully(self, tmp_path):
        """Test that deletion errors are handled gracefully."""
        # Create user directory
        user_dir = tmp_path / "data" / "files" / "user_1"
        user_dir.mkdir(parents=True)
        
        # Create an old file
        old_file = user_dir / "test_20240101-120000_abc12345.txt"
        old_file.write_text("old content")
        
        # Make the file old
        old_time = time.time() - (25 * 3600)
        import os
        os.utime(old_file, (old_time, old_time))
        
        # Mock unlink to raise an exception
        original_unlink = Path.unlink
        def mock_unlink(self, *args, **kwargs):
            raise PermissionError("Cannot delete file")
        
        async def mock_get_or_none(**kwargs):
            return None
        
        with patch.object(Upload, 'get_or_none', side_effect=mock_get_or_none):
            with patch.object(Path, 'unlink', mock_unlink):
                with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
                    with patch.object(config, 'storage_orphaned_max_age_hours', 24):
                        # Should not raise exception
                        orphans_found = await cleanup_orphaned_files()
        
        # File should still exist due to permission error
        assert old_file.exists()
        # Counter should still increment even if deletion fails
        assert orphans_found == 1

    async def test_cleanup_returns_correct_count(self, tmp_path):
        """Test that cleanup returns the correct count of orphaned files."""
        # Create user directory
        user_dir = tmp_path / "data" / "files" / "user_1"
        user_dir.mkdir(parents=True)
        
        # Create multiple old files
        old_files = []
        for i in range(5):
            old_file = user_dir / f"test{i}_20240101-120000_abc1234{i}.txt"
            old_file.write_text(f"content{i}")
            old_files.append(old_file)
        
        # Make files old
        old_time = time.time() - (25 * 3600)
        import os
        for old_file in old_files:
            os.utime(old_file, (old_time, old_time))
        
        # Mock Upload.get_or_none to return None (no DB records)
        async def mock_get_or_none(**kwargs):
            return None
        
        with patch.object(Upload, 'get_or_none', side_effect=mock_get_or_none):
            with patch.object(config, 'storage_path', tmp_path / "data" / "files"):
                with patch.object(config, 'storage_orphaned_max_age_hours', 24):
                    orphans_found = await cleanup_orphaned_files()
        
        # All files should be deleted
        for old_file in old_files:
            assert not old_file.exists()
        assert orphans_found == 5
