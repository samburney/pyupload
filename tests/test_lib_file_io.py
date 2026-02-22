"""Tests for app/lib/file_io.py — pure I/O utilities (no DB dependencies)."""

import pytest
from io import BytesIO
from pathlib import Path
from tempfile import SpooledTemporaryFile
from unittest.mock import patch

from fastapi import UploadFile

from app.lib.file_io import (
    delete_file,
    get_file_instance,
    get_file_mime_type,
    get_file_size,
    get_filename,
)


# ============================================================================
# get_filename
# ============================================================================

class TestGetFilename:
    """Tests for get_filename()."""

    def test_extracts_filename_from_upload_file(self):
        """Returns filename attribute from an UploadFile."""
        upload = UploadFile(file=BytesIO(b"data"), filename="photo.jpg")
        assert get_filename(upload) == "photo.jpg"

    def test_uses_explicit_filename_when_provided(self):
        """Explicit filename overrides any file attribute."""
        upload = UploadFile(file=BytesIO(b"data"), filename="original.jpg")
        assert get_filename(upload, filename="override.png") == "override.png"

    def test_uses_explicit_filename_for_binary_io(self):
        """Explicit filename can supply a name for a plain BinaryIO."""
        bio = BytesIO(b"data")
        assert get_filename(bio, filename="manual.txt") == "manual.txt"

    def test_raises_value_error_when_no_filename_available(self):
        """Raises ValueError when the file has no filename and none is supplied."""
        bio = BytesIO(b"data")
        with pytest.raises(ValueError):
            get_filename(bio)

    def test_raises_value_error_for_upload_file_with_no_filename(self):
        """Raises ValueError when UploadFile.filename is None and no override given."""
        upload = UploadFile(file=BytesIO(b"data"), filename=None)
        with pytest.raises(ValueError):
            get_filename(upload)


# ============================================================================
# get_file_instance
# ============================================================================

class TestGetFileInstance:
    """Tests for get_file_instance()."""

    def test_returns_underlying_file_from_upload_file(self):
        """Returns the underlying BinaryIO from an UploadFile."""
        bio = BytesIO(b"data")
        upload = UploadFile(file=bio, filename="test.txt")
        instance = get_file_instance(upload)
        assert instance is bio

    def test_returns_spooled_temp_file_directly(self):
        """Returns a SpooledTemporaryFile as-is."""
        with SpooledTemporaryFile(max_size=1024) as stf:
            stf.write(b"data")
            stf.seek(0)
            instance = get_file_instance(stf)
            assert instance is stf

    def test_returns_binary_io_directly(self):
        """Returns a plain BinaryIO as-is."""
        bio = BytesIO(b"content")
        instance = get_file_instance(bio)
        assert instance is bio

    def test_raises_type_error_for_invalid_input(self):
        """Raises TypeError for objects that are not file-like."""
        with pytest.raises(TypeError):
            get_file_instance("not a file")  # type: ignore


# ============================================================================
# get_file_size
# ============================================================================

class TestGetFileSize:
    """Tests for get_file_size()."""

    def test_returns_correct_size_for_binary_io(self):
        """Returns the byte length of a BytesIO buffer."""
        content = b"Hello, World!"
        assert get_file_size(BytesIO(content)) == len(content)

    def test_returns_zero_for_empty_file(self):
        """Returns 0 for an empty BytesIO."""
        assert get_file_size(BytesIO(b"")) == 0

    def test_returns_correct_size_for_large_file(self):
        """Returns correct size for a 1 MiB buffer."""
        content = b"x" * (1024 * 1024)
        assert get_file_size(BytesIO(content)) == 1024 * 1024

    def test_preserves_file_position(self):
        """Does not alter the caller's file position."""
        bio = BytesIO(b"Hello, World!")
        bio.seek(5)
        get_file_size(bio)
        assert bio.tell() == 5

    @pytest.mark.asyncio
    async def test_returns_correct_size_for_upload_file(self):
        """Works correctly when given an UploadFile."""
        content = b"Hello, World!"
        upload = UploadFile(file=BytesIO(content), filename="test.txt")
        assert get_file_size(upload) == len(content)


# ============================================================================
# get_file_mime_type
# ============================================================================

class TestGetFileMimeType:
    """Tests for get_file_mime_type()."""

    @pytest.mark.asyncio
    async def test_detects_jpeg_mime_type(self):
        """Detects image/jpeg for a PIL-generated JPEG."""
        from PIL import Image as PILImage
        buf = BytesIO()
        PILImage.new("RGB", (10, 10), color="red").save(buf, format="JPEG")
        buf.seek(0)
        mime = await get_file_mime_type(buf)
        assert mime == "image/jpeg"

    @pytest.mark.asyncio
    async def test_raises_value_error_for_empty_file(self):
        """Raises ValueError when the file is empty."""
        with pytest.raises(ValueError, match="empty"):
            await get_file_mime_type(BytesIO(b""))

    @pytest.mark.asyncio
    async def test_restores_position_after_read(self):
        """Leaves the file at its original position after detection."""
        content = b"Hello, plain text content"
        bio = BytesIO(content)
        bio.seek(10)
        await get_file_mime_type(bio)
        assert bio.tell() == 10

    @pytest.mark.asyncio
    async def test_works_with_upload_file(self):
        """Works correctly when given an UploadFile wrapping a PIL-generated JPEG."""
        from PIL import Image as PILImage
        buf = BytesIO()
        PILImage.new("RGB", (10, 10), color="blue").save(buf, format="JPEG")
        buf.seek(0)
        upload = UploadFile(file=buf, filename="test.jpg")
        mime = await get_file_mime_type(upload)
        assert mime == "image/jpeg"


# ============================================================================
# delete_file
# ============================================================================

class TestDeleteFile:
    """Tests for delete_file()."""

    def test_deletes_existing_file_and_returns_true(self, tmp_path):
        """Returns True and removes the file when it exists."""
        f = tmp_path / "test.txt"
        f.write_text("data")

        result = delete_file(f)

        assert result is True
        assert not f.exists()

    def test_returns_false_when_file_missing(self, tmp_path):
        """Returns False (does not raise) when the file does not exist."""
        f = tmp_path / "missing.txt"

        result = delete_file(f)

        assert result is False

    def test_deletes_cached_variants_matching_stem(self, tmp_path):
        """Removes files in the cache/ subdirectory whose names start with stem-."""
        f = tmp_path / "photo.jpg"
        f.write_text("original data")

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cached_small = cache_dir / "photo-100x100.jpg"
        cached_large = cache_dir / "photo-800x600.webp"
        unrelated = cache_dir / "other-100x100.jpg"
        cached_small.write_text("small")
        cached_large.write_text("large")
        unrelated.write_text("other")

        delete_file(f)

        assert not cached_small.exists()
        assert not cached_large.exists()
        assert unrelated.exists()  # Unrelated file must be preserved

    def test_handles_missing_cache_directory_gracefully(self, tmp_path):
        """Does not fail when no cache/ directory exists alongside the file."""
        f = tmp_path / "test.txt"
        f.write_text("data")

        result = delete_file(f)

        assert result is True
        assert not f.exists()

    def test_handles_empty_cache_directory(self, tmp_path):
        """Works correctly when the cache/ directory exists but is empty."""
        f = tmp_path / "test.txt"
        f.write_text("data")
        (tmp_path / "cache").mkdir()

        result = delete_file(f)

        assert result is True
        assert not f.exists()

    def test_handles_permission_error_on_main_file(self, tmp_path):
        """Does not raise when the main file cannot be deleted."""
        f = tmp_path / "locked.txt"
        f.write_text("data")

        with patch.object(Path, "unlink", side_effect=PermissionError("locked")):
            result = delete_file(f)

        # Returns False because deletion failed
        assert result is False

    def test_cached_variants_still_deleted_even_when_main_file_error(self, tmp_path):
        """Attempts to delete cached variants even if the main file deletion fails."""
        f = tmp_path / "photo.jpg"
        f.write_text("original")

        cache_dir = tmp_path / "cache"
        cache_dir.mkdir()
        cached = cache_dir / "photo-thumb.jpg"
        cached.write_text("thumb")

        original_unlink = Path.unlink

        def selective_unlink(self_path, *args, **kwargs):
            if self_path == f:
                raise PermissionError("locked")
            return original_unlink(self_path, *args, **kwargs)

        with patch.object(Path, "unlink", selective_unlink):
            delete_file(f)

        # Cached variant should be deleted even though main file fails
        assert not cached.exists()
