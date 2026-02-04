"""Tests for app/lib/file_serving.py functions."""

import pytest
from pathlib import Path
from fastapi.responses import FileResponse

from app.lib.file_serving import (
    is_inline_mimetype,
    serve_file,
    NotAuthorisedError,
    ALLOWED_INLINE_MIMETYPES,
)
from app.lib.config import get_app_config
from app.models.users import User
from app.models.uploads import Upload


class TestIsInlineMimetype:
    """Test is_inline_mimetype function."""

    def test_image_wildcard_matches(self):
        """Test that image/* wildcard matches image MIME types."""
        assert is_inline_mimetype("image/jpeg") is True
        assert is_inline_mimetype("image/png") is True
        assert is_inline_mimetype("image/gif") is True
        assert is_inline_mimetype("image/webp") is True
        assert is_inline_mimetype("image/svg+xml") is True

    def test_video_wildcard_matches(self):
        """Test that video/* wildcard matches video MIME types."""
        assert is_inline_mimetype("video/mp4") is True
        assert is_inline_mimetype("video/webm") is True
        assert is_inline_mimetype("video/ogg") is True
        assert is_inline_mimetype("video/quicktime") is True

    def test_audio_wildcard_matches(self):
        """Test that audio/* wildcard matches audio MIME types."""
        assert is_inline_mimetype("audio/mpeg") is True
        assert is_inline_mimetype("audio/ogg") is True
        assert is_inline_mimetype("audio/wav") is True
        assert is_inline_mimetype("audio/webm") is True

    def test_exact_matches(self):
        """Test that exact MIME types match."""
        assert is_inline_mimetype("application/pdf") is True
        assert is_inline_mimetype("text/plain") is True

    def test_non_inline_types(self):
        """Test that non-inline MIME types return False."""
        assert is_inline_mimetype("application/zip") is False
        assert is_inline_mimetype("application/octet-stream") is False
        assert is_inline_mimetype("application/json") is False
        assert is_inline_mimetype("text/html") is False

    def test_case_sensitivity(self):
        """Test MIME type matching is case-sensitive (as per spec)."""
        # MIME types should be lowercase per RFC
        assert is_inline_mimetype("image/jpeg") is True
        # Uppercase should not match (though browsers may be lenient)
        assert is_inline_mimetype("IMAGE/JPEG") is False


class TestServeFile:
    """Test serve_file function."""

    @pytest.mark.asyncio
    async def test_serve_public_file_anonymous_user(self, db, tmp_path, monkeypatch):
        """Test serving a public file to an anonymous user."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="fileowner",
            email="owner@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        # Create a test file
        test_file = tmp_path / f"user_{user.id}" / "test_file.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("test content")

        upload = await Upload.create(
            user=user,
            description="Test file",
            name="test_file",
            cleanname="test",
            originalname="test.txt",
            ext="txt",
            size=12,
            type="text/plain",
            extra="",
            private=0,
        )

        # Serve file to anonymous user
        response = await serve_file(upload, filename=None, user=None, download=False)

        assert isinstance(response, FileResponse)
        assert response.media_type == "text/plain"

    @pytest.mark.asyncio
    async def test_serve_private_file_to_owner(self, db, tmp_path, monkeypatch):
        """Test serving a private file to the owner."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="privateowner",
            email="private@example.com",
            password="password",
            fingerprint_hash="fp-hash-private",
        )

        # Create a test file
        test_file = tmp_path / f"user_{user.id}" / "private_file.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("private content")

        upload = await Upload.create(
            user=user,
            description="Private file",
            name="private_file",
            cleanname="private",
            originalname="private.txt",
            ext="txt",
            size=15,
            type="text/plain",
            extra="",
            private=1,
        )

        # Serve file to owner
        response = await serve_file(upload, filename=None, user=user, download=False)

        assert isinstance(response, FileResponse)

    @pytest.mark.asyncio
    async def test_serve_private_file_to_anonymous_raises_error(self, db):
        """Test that serving a private file to anonymous user raises NotAuthorisedError."""
        user = await User.create(
            username="privateowner2",
            email="private2@example.com",
            password="password",
            fingerprint_hash="fp-hash-private2",
        )

        upload = await Upload.create(
            user=user,
            description="Private file",
            name="private_file2",
            cleanname="private2",
            originalname="private2.txt",
            ext="txt",
            size=15,
            type="text/plain",
            extra="",
            private=1,
        )

        # Attempt to serve private file to anonymous user
        with pytest.raises(NotAuthorisedError):
            await serve_file(upload, filename=None, user=None, download=False)

    @pytest.mark.asyncio
    async def test_serve_private_file_to_different_user_raises_error(self, db):
        """Test that serving a private file to a different user raises NotAuthorisedError."""
        owner = await User.create(
            username="owner",
            email="owner@example.com",
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
            name="private_file3",
            cleanname="private3",
            originalname="private3.txt",
            ext="txt",
            size=15,
            type="text/plain",
            extra="",
            private=1,
        )

        # Attempt to serve private file to different user
        with pytest.raises(NotAuthorisedError):
            await serve_file(upload, filename=None, user=other_user, download=False)

    @pytest.mark.asyncio
    async def test_serve_nonexistent_file_raises_error(self, db):
        """Test that serving a non-existent file raises FileNotFoundError."""
        user = await User.create(
            username="nofileuser",
            email="nofile@example.com",
            password="password",
            fingerprint_hash="fp-hash-nofile",
        )

        upload = await Upload.create(
            user=user,
            description="Non-existent file",
            name="nonexistent_file",
            cleanname="nonexistent",
            originalname="nonexistent.txt",
            ext="txt",
            size=0,
            type="text/plain",
            extra="",
            private=0,
        )

        # File doesn't exist on disk
        with pytest.raises(FileNotFoundError):
            await serve_file(upload, filename=None, user=None, download=False)

    @pytest.mark.asyncio
    async def test_view_counter_increments_for_non_owner(self, db, tmp_path, monkeypatch):
        """Test that view counter increments when non-owner accesses file."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="viewcountowner",
            email="viewcount@example.com",
            password="password",
            fingerprint_hash="fp-hash-viewcount",
        )

        # Create a test file
        test_file = tmp_path / f"user_{user.id}" / "view_test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("view test content")

        upload = await Upload.create(
            user=user,
            description="View counter test",
            name="view_test",
            cleanname="view",
            originalname="view.txt",
            ext="txt",
            size=17,
            type="text/plain",
            extra="",
            private=0,
            viewed=0,
        )

        initial_views = upload.viewed

        # Serve file to anonymous user
        await serve_file(upload, filename=None, user=None, download=False)

        # Refresh from database
        await upload.refresh_from_db()
        assert upload.viewed == initial_views + 1

    @pytest.mark.asyncio
    async def test_view_counter_does_not_increment_for_owner(self, db, tmp_path, monkeypatch):
        """Test that view counter does not increment when owner accesses file."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="ownerview",
            email="ownerview@example.com",
            password="password",
            fingerprint_hash="fp-hash-ownerview",
        )

        # Create a test file
        test_file = tmp_path / f"user_{user.id}" / "owner_view.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("owner view test")

        upload = await Upload.create(
            user=user,
            description="Owner view test",
            name="owner_view",
            cleanname="owner",
            originalname="owner.txt",
            ext="txt",
            size=15,
            type="text/plain",
            extra="",
            private=0,
            viewed=0,
        )

        initial_views = upload.viewed

        # Serve file to owner
        await serve_file(upload, filename=None, user=user, download=False)

        # Refresh from database
        await upload.refresh_from_db()
        assert upload.viewed == initial_views  # Should not increment

    @pytest.mark.asyncio
    async def test_content_disposition_inline_for_images(self, db, tmp_path, monkeypatch):
        """Test that Content-Disposition is inline for image files."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="imageuser",
            email="image@example.com",
            password="password",
            fingerprint_hash="fp-hash-image",
        )

        # Create a test image file
        test_file = tmp_path / f"user_{user.id}" / "test_image.jpg"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake image data")

        upload = await Upload.create(
            user=user,
            description="Test image",
            name="test_image",
            cleanname="test",
            originalname="test.jpg",
            ext="jpg",
            size=15,
            type="image/jpeg",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert "inline" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_content_disposition_attachment_when_download_true(self, db, tmp_path, monkeypatch):
        """Test that Content-Disposition is attachment when download=True."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="downloaduser",
            email="download@example.com",
            password="password",
            fingerprint_hash="fp-hash-download",
        )

        # Create a test file
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

        response = await serve_file(upload, filename=None, user=None, download=True)

        assert "attachment" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_custom_filename_sanitization(self, db, tmp_path, monkeypatch):
        """Test that custom filenames are sanitized."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="sanitizeuser",
            email="sanitize@example.com",
            password="password",
            fingerprint_hash="fp-hash-sanitize",
        )

        # Create a test file
        test_file = tmp_path / f"user_{user.id}" / "sanitize_test.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("sanitize test")

        upload = await Upload.create(
            user=user,
            description="Sanitize test",
            name="sanitize_test",
            cleanname="sanitize",
            originalname="sanitize.txt",
            ext="txt",
            size=14,
            type="text/plain",
            extra="",
            private=0,
        )

        # Try to serve with malicious filename
        response = await serve_file(upload, filename="../../etc/passwd", user=None, download=False)

        # Filename should be sanitized to just "passwd"
        assert "passwd" in response.headers["Content-Disposition"]
        assert ".." not in response.headers["Content-Disposition"]
        assert "/" not in response.headers["Content-Disposition"]


class TestCacheControlHeaders:
    """Test Cache-Control header behavior."""

    @pytest.mark.asyncio
    async def test_cache_control_private_for_private_files(self, db, tmp_path, monkeypatch):
        """Test that private files get Cache-Control: private header."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="privatecache",
            email="privatecache@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        # Create a test file
        test_file = tmp_path / f"user_{user.id}" / "private_cache.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("private content")

        upload = await Upload.create(
            user=user,
            description="Private cache test",
            name="private_cache",
            cleanname="privatecache",
            originalname="privatecache.txt",
            ext="txt",
            size=15,
            type="text/plain",
            extra="",
            private=1,
        )

        response = await serve_file(upload, filename=None, user=user, download=False)

        assert "Cache-Control" in response.headers
        assert "private" in response.headers["Cache-Control"]
        assert "max-age=3600" in response.headers["Cache-Control"]

    @pytest.mark.asyncio
    async def test_cache_control_public_for_public_files(self, db, tmp_path, monkeypatch):
        """Test that public files get Cache-Control: public header."""
        # Mock storage path
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="publiccache",
            email="publiccache@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        # Create a test file
        test_file = tmp_path / f"user_{user.id}" / "public_cache.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("public content")

        upload = await Upload.create(
            user=user,
            description="Public cache test",
            name="public_cache",
            cleanname="publiccache",
            originalname="publiccache.txt",
            ext="txt",
            size=14,
            type="text/plain",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert "Cache-Control" in response.headers
        assert "public" in response.headers["Cache-Control"]
        assert "max-age=3600" in response.headers["Cache-Control"]


class TestContentDispositionVariety:
    """Test Content-Disposition header for various MIME types."""

    @pytest.mark.asyncio
    async def test_inline_for_video_files(self, db, tmp_path, monkeypatch):
        """Test that video files are served inline by default."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="videouser",
            email="video@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "test_video.mp4"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake video data")

        upload = await Upload.create(
            user=user,
            description="Test video",
            name="test_video",
            cleanname="test",
            originalname="test.mp4",
            ext="mp4",
            size=15,
            type="video/mp4",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert "inline" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_inline_for_audio_files(self, db, tmp_path, monkeypatch):
        """Test that audio files are served inline by default."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="audiouser",
            email="audio@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "test_audio.mp3"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake audio data")

        upload = await Upload.create(
            user=user,
            description="Test audio",
            name="test_audio",
            cleanname="test",
            originalname="test.mp3",
            ext="mp3",
            size=15,
            type="audio/mpeg",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert "inline" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_inline_for_pdf_files(self, db, tmp_path, monkeypatch):
        """Test that PDF files are served inline by default."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="pdfuser",
            email="pdf@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "test_doc.pdf"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake pdf data")

        upload = await Upload.create(
            user=user,
            description="Test PDF",
            name="test_doc",
            cleanname="test",
            originalname="test.pdf",
            ext="pdf",
            size=13,
            type="application/pdf",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert "inline" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_attachment_for_binary_files(self, db, tmp_path, monkeypatch):
        """Test that binary files are served as attachment by default."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="binaryuser",
            email="binary@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "test_binary.bin"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake binary data")

        upload = await Upload.create(
            user=user,
            description="Test binary",
            name="test_binary",
            cleanname="test",
            originalname="test.bin",
            ext="bin",
            size=16,
            type="application/octet-stream",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert "attachment" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_attachment_for_zip_files(self, db, tmp_path, monkeypatch):
        """Test that archive files are served as attachment."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="zipuser",
            email="zip@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "test_archive.zip"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake zip data")

        upload = await Upload.create(
            user=user,
            description="Test ZIP",
            name="test_archive",
            cleanname="test",
            originalname="test.zip",
            ext="zip",
            size=13,
            type="application/zip",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert "attachment" in response.headers["Content-Disposition"]

    @pytest.mark.asyncio
    async def test_download_param_forces_attachment_for_all_types(self, db, tmp_path, monkeypatch):
        """Test that download=True forces attachment even for inline types."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="forcedownload",
            email="forcedownload@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        # Test with an image (normally inline)
        test_file = tmp_path / f"user_{user.id}" / "force_download.png"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake image")

        upload = await Upload.create(
            user=user,
            description="Force download test",
            name="force_download",
            cleanname="force",
            originalname="force.png",
            ext="png",
            size=10,
            type="image/png",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=True)

        assert "attachment" in response.headers["Content-Disposition"]


class TestMimeTypeHandling:
    """Test MIME type handling in FileResponse."""

    @pytest.mark.asyncio
    async def test_correct_mime_type_for_images(self, db, tmp_path, monkeypatch):
        """Test that image MIME type is set correctly."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="mimeimageuser",
            email="mimeimage@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "mime_test.jpg"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake image")

        upload = await Upload.create(
            user=user,
            description="MIME test",
            name="mime_test",
            cleanname="mime",
            originalname="mime.jpg",
            ext="jpg",
            size=10,
            type="image/jpeg",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert response.media_type == "image/jpeg"

    @pytest.mark.asyncio
    async def test_correct_mime_type_for_videos(self, db, tmp_path, monkeypatch):
        """Test that video MIME type is set correctly."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="mimevideouser",
            email="mimevideo@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "mime_video.mp4"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake video")

        upload = await Upload.create(
            user=user,
            description="MIME video test",
            name="mime_video",
            cleanname="mimevideo",
            originalname="mimevideo.mp4",
            ext="mp4",
            size=10,
            type="video/mp4",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert response.media_type == "video/mp4"

    @pytest.mark.asyncio
    async def test_correct_mime_type_for_audio(self, db, tmp_path, monkeypatch):
        """Test that audio MIME type is set correctly."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="mimeaudiouser",
            email="mimeaudio@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "mime_audio.mp3"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake audio")

        upload = await Upload.create(
            user=user,
            description="MIME audio test",
            name="mime_audio",
            cleanname="mimeaudio",
            originalname="mimeaudio.mp3",
            ext="mp3",
            size=10,
            type="audio/mpeg",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert response.media_type == "audio/mpeg"

    @pytest.mark.asyncio
    async def test_correct_mime_type_for_pdf(self, db, tmp_path, monkeypatch):
        """Test that PDF MIME type is set correctly."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="mimepdfuser",
            email="mimepdf@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "mime_doc.pdf"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_bytes(b"fake pdf")

        upload = await Upload.create(
            user=user,
            description="MIME PDF test",
            name="mime_doc",
            cleanname="mimedoc",
            originalname="mimedoc.pdf",
            ext="pdf",
            size=8,
            type="application/pdf",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert response.media_type == "application/pdf"

    @pytest.mark.asyncio
    async def test_correct_mime_type_for_text(self, db, tmp_path, monkeypatch):
        """Test that text MIME type is set correctly."""
        config = get_app_config()
        monkeypatch.setattr(config, "storage_path", tmp_path)

        user = await User.create(
            username="mimetextuser",
            email="mimetext@example.com",
            password="password",
            fingerprint_hash="fp-hash",
        )

        test_file = tmp_path / f"user_{user.id}" / "mime_text.txt"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("test text content")

        upload = await Upload.create(
            user=user,
            description="MIME text test",
            name="mime_text",
            cleanname="mimetext",
            originalname="mimetext.txt",
            ext="txt",
            size=17,
            type="text/plain",
            extra="",
            private=0,
        )

        response = await serve_file(upload, filename=None, user=None, download=False)

        assert response.media_type == "text/plain"
