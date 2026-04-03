"""
Tests for computed filepath, URL, and extension properties on Upload and UploadMetadata.

- make_user_filepath function behaviour and directory creation
- Upload.filepath, Upload.url, Upload.download_url, and Upload.dot_ext properties
- UploadMetadata.filepath property
"""
import pytest
from pathlib import Path

from app.models.users import User
from app.models.uploads import Upload, UploadMetadata, make_user_filepath
from app.lib.config import get_app_config

config = get_app_config()


class TestMakeUserFilepath:
    """Test make_user_filepath function."""

    def test_make_user_filepath_basic(self):
        """Test basic filepath generation."""
        filepath = make_user_filepath(42, "document_20250124-063307_abcd1234")
        assert isinstance(filepath, Path)
        assert str(filepath).endswith("user_42/document_20250124-063307_abcd1234")

    def test_make_user_filepath_creates_directory(self):
        """Test that make_user_filepath creates the user directory."""
        filepath = make_user_filepath(123, "file_20250124-063307_a1b2c3d4")
        assert isinstance(filepath, Path)
        # Directory should be created
        assert filepath.parent.exists()
        assert filepath.parent.is_dir()
        assert "user_123" in str(filepath.parent)

    def test_make_user_filepath_different_users_different_paths(self):
        """Test that different user IDs generate different paths."""
        filepath1 = make_user_filepath(1, "file_20250124-063307_abcd1234")
        filepath2 = make_user_filepath(2, "file_20250124-063307_abcd1234")

        assert filepath1 != filepath2
        assert "user_1" in str(filepath1)
        assert "user_2" in str(filepath2)

    def test_make_user_filepath_same_user_different_files(self):
        """Test that same user ID with different filenames generates child paths in same directory."""
        filepath1 = make_user_filepath(99, "file1_20250124-063307_abcd1234")
        filepath2 = make_user_filepath(99, "file2_20250124-063307_efgh5678")

        # Both should be in user_99 directory but different files
        assert filepath1.parent == filepath2.parent
        assert filepath1.name != filepath2.name
        assert filepath1 != filepath2

    def test_make_user_filepath_idempotent_directory_creation(self):
        """Test that calling make_user_filepath twice with same user doesn't fail."""
        # First call should create directory
        filepath1 = make_user_filepath(77, "file1_20250124-063307_abcd1234")
        # Second call should succeed without error (mkdir with exist_ok=True)
        filepath2 = make_user_filepath(77, "file2_20250124-063307_efgh5678")

        assert filepath1.parent.exists()
        assert filepath2.parent.exists()
        assert filepath1.parent == filepath2.parent


class TestUploadFilepathProperty:
    """Test Upload model filepath property."""

    async def test_upload_filepath_property_returns_path(self, db):
        """Test Upload filepath property returns a Path object."""
        user = await User.create(
            username="pathtest",
            email="path@example.com",
            password="hashed_password_path",
            fingerprint_hash="fp-hash-path",
        )

        upload = await Upload.create(
            user=user,
            description="Path test",
            name="testfile_20250124-063307_abcd1234",
            cleanname="testfile",
            originalname="testfile.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        filepath = upload.filepath
        assert isinstance(filepath, Path)

    async def test_upload_filepath_property_contains_user_id(self, db):
        """Test Upload filepath property contains correct user ID."""
        user = await User.create(
            username="pathtest2",
            email="path2@example.com",
            password="hashed_password_path2",
            fingerprint_hash="fp-hash-path2",
        )

        upload = await Upload.create(
            user=user,
            description="Path test 2",
            name="testfile_20250124-063307_abcd1234",
            cleanname="testfile",
            originalname="testfile.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        filepath = upload.filepath
        assert f"user_{user.id}" in str(filepath)

    async def test_upload_filepath_property_contains_filename(self, db):
        """Test Upload filepath property contains the upload name and extension."""
        user = await User.create(
            username="pathtest3",
            email="path3@example.com",
            password="hashed_password_path3",
            fingerprint_hash="fp-hash-path3",
        )

        filename = "myfile_20250124-063307_abcd1234"
        upload = await Upload.create(
            user=user,
            description="Path test 3",
            name=filename,
            cleanname="myfile",
            originalname="myfile.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        filepath = upload.filepath
        assert filename in str(filepath)
        # Verify extension is included in filepath
        assert str(filepath).endswith("txt")
        assert f"{filename}.txt" in str(filepath)

    async def test_upload_filepath_property_different_uploads_different_paths(self, db):
        """Test different uploads have different filepath properties."""
        user = await User.create(
            username="pathtest4",
            email="path4@example.com",
            password="hashed_password_path4",
            fingerprint_hash="fp-hash-path4",
        )

        upload1 = await Upload.create(
            user=user,
            description="Test 1",
            name="file1_20250124-063307_a1a1a1a1",
            cleanname="file1",
            originalname="file1.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        upload2 = await Upload.create(
            user=user,
            description="Test 2",
            name="file2_20250124-063307_b2b2b2b2",
            cleanname="file2",
            originalname="file2.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        filepath1 = upload1.filepath
        filepath2 = upload2.filepath

        assert filepath1 != filepath2
        assert filepath1.parent == filepath2.parent  # Same user directory
        assert filepath1.name != filepath2.name  # Different filenames


class TestUploadUrlProperties:
    """Test Upload model url and download_url properties."""

    async def test_upload_url_property(self, db):
        """Test Upload url property returns correct download URL."""
        user = await User.create(
            username="urltest",
            email="url@example.com",
            password="hashed_password_url",
            fingerprint_hash="fp-hash-url",
        )

        upload = await Upload.create(
            user=user,
            description="URL test",
            name="testfile_20250124-063307_abcd1234",
            cleanname="testfile",
            originalname="testfile.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        # Expected format: {base_url}/get/{id}/{cleanname}.{ext}
        expected_url = f"{config.app_base_url}/get/{upload.id}/testfile.txt"
        assert upload.url == expected_url

    async def test_upload_download_url_property(self, db):
        """Test Upload download_url property returns correct download URL."""
        user = await User.create(
            username="statictest",
            email="static@example.com",
            password="hashed_password_static",
            fingerprint_hash="fp-hash-static",
        )

        upload = await Upload.create(
            user=user,
            description="Static URL test",
            name="image_20250124-063307_12345678",
            cleanname="image",
            originalname="image.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="0",
        )

        # Expected format: {base_url}/download/{id}/{cleanname}.{ext}
        expected_url = f"{config.app_base_url}/download/{upload.id}/image.jpg"
        assert upload.download_url == expected_url

        # Verify url exists (basic check, implementation may vary)
        assert upload.url is not None


    async def test_upload_url_properties_without_extension(self, db):
        """Test URL properties handle files without extensions correctly."""
        user = await User.create(
            username="noext",

            email="noext@example.com",
            password="hashed_password_noext",
            fingerprint_hash="fp-hash-noext",
        )

        upload = await Upload.create(
            user=user,
            description="No extension test",
            name="README_20250124-063307_abcdef12",
            cleanname="README",
            originalname="README",
            ext="",
            size=128,
            type="text/plain",
            extra="0",
        )

        # Should not have a trailing dot
        assert upload.url == f"{config.app_base_url}/get/{upload.id}/README"
        assert upload.download_url == f"{config.app_base_url}/download/{upload.id}/README"


class TestUploadDotExtProperty:
    """Test Upload model dot_ext property."""

    async def test_dot_ext_with_extension(self, db):
        """Test dot_ext property returns dot plus extension when extension exists."""
        user = await User.create(
            username="dotexttest",
            email="dotext@example.com",
            password="hashed_password",
            fingerprint_hash="fp-hash",
        )

        upload = await Upload.create(
            user=user,
            description="Dot ext test",
            name="testfile_20250124-063307_abcd1234",
            cleanname="testfile",
            originalname="testfile.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        assert upload.dot_ext == ".txt"

    async def test_dot_ext_without_extension(self, db):
        """Test dot_ext property returns empty string when no extension."""
        user = await User.create(
            username="dotexttest2",
            email="dotext2@example.com",
            password="hashed_password",
            fingerprint_hash="fp-hash-2",
        )

        upload = await Upload.create(
            user=user,
            description="No ext test",
            name="README_20250124-063307_abcd1234",
            cleanname="README",
            originalname="README",
            ext="",
            size=128,
            type="text/plain",
            extra="0",
        )

        assert upload.dot_ext == ""

    async def test_dot_ext_with_multipart_extension(self, db):
        """Test dot_ext property with multipart extensions like tar.gz."""
        user = await User.create(
            username="dotexttest3",
            email="dotext3@example.com",
            password="hashed_password",
            fingerprint_hash="fp-hash-3",
        )

        upload = await Upload.create(
            user=user,
            description="Multipart ext test",
            name="archive_20250124-063307_abcd1234",
            cleanname="archive",
            originalname="archive.tar.gz",
            ext="tar.gz",
            size=2048,
            type="application/gzip",
            extra="0",
        )

        assert upload.dot_ext == ".tar.gz"

    async def test_filename_property_uses_dot_ext(self, db):
        """Test that filename property correctly uses dot_ext."""
        user = await User.create(
            username="filenametest",
            email="filename@example.com",
            password="hashed_password",
            fingerprint_hash="fp-hash-filename",
        )

        upload = await Upload.create(
            user=user,
            description="Filename test",
            name="myfile_20250124-063307_abcd1234",
            cleanname="myfile",
            originalname="myfile.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="0",
        )

        assert upload.filename == "myfile_20250124-063307_abcd1234.jpg"
        assert upload.filename == f"{upload.name}{upload.dot_ext}"


class TestUploadMetadataFilepathProperty:
    """Test UploadMetadata model filepath property."""

    def test_uploadmetadata_filepath_returns_path(self):
        """Test UploadMetadata filepath property returns a Path object."""
        metadata = UploadMetadata(
            user_id=42,
            filename="test_20250124-063307_abcd1234",
            ext="txt",
            original_filename="test.txt",
            clean_filename="test",
            size=100,
            mime_type="text/plain",
        )

        filepath = metadata.filepath
        assert isinstance(filepath, Path)

    def test_uploadmetadata_filepath_contains_user_id(self):
        """Test UploadMetadata filepath contains correct user ID."""
        user_id = 123
        metadata = UploadMetadata(
            user_id=user_id,
            filename="test_20250124-063307_abcd1234",
            ext="txt",
            original_filename="test.txt",
            clean_filename="test",
            size=100,
            mime_type="text/plain",
        )

        filepath = metadata.filepath
        assert f"user_{user_id}" in str(filepath)

    def test_uploadmetadata_filepath_contains_filename(self):
        """Test UploadMetadata filepath contains the filename and extension."""
        filename = "document_20250124-063307_a1b2c3d4"
        metadata = UploadMetadata(
            user_id=42,
            filename=filename,
            ext="pdf",
            original_filename="document.pdf",
            clean_filename="document",
            size=2048,
            mime_type="application/pdf",
        )

        filepath = metadata.filepath
        assert filename in str(filepath)
        # Verify extension is included in filepath
        assert str(filepath).endswith("pdf")
        assert f"{filename}.pdf" in str(filepath)

    def test_uploadmetadata_filepath_creates_user_directory(self):
        """Test UploadMetadata filepath creates user directory."""
        user_id = 999
        metadata = UploadMetadata(
            user_id=user_id,
            filename="test_20250124-063307_abcd1234",
            ext="txt",
            original_filename="test.txt",
            clean_filename="test",
            size=100,
            mime_type="text/plain",
        )

        filepath = metadata.filepath
        # Directory should be created
        assert filepath.parent.exists()
        assert filepath.parent.is_dir()

    def test_uploadmetadata_filepath_different_metadata_different_paths(self):
        """Test different metadata instances have different filepaths."""
        metadata1 = UploadMetadata(
            user_id=42,
            filename="file1_20250124-063307_a1a1a1a1",
            ext="txt",
            original_filename="file1.txt",
            clean_filename="file1",
            size=100,
            mime_type="text/plain",
        )

        metadata2 = UploadMetadata(
            user_id=42,
            filename="file2_20250124-063307_b2b2b2b2",
            ext="txt",
            original_filename="file2.txt",
            clean_filename="file2",
            size=100,
            mime_type="text/plain",
        )

        filepath1 = metadata1.filepath
        filepath2 = metadata2.filepath

        assert filepath1 != filepath2
        assert filepath1.parent == filepath2.parent  # Same user directory
        assert filepath1.name != filepath2.name
