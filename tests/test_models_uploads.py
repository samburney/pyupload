"""
Tests for Upload, UploadMetadata, and UploadResult models.

Validates:
- Upload model creation and persistence
- UploadMetadata Pydantic validation (filename pattern, MIME type)
- UploadResult structure for API responses
- Model table mapping and field defaults
- TimestampMixin functionality
- Filepath generation for upload storage
"""
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import ValidationError

from app.models.users import User
from app.models.uploads import Upload, UploadMetadata, UploadResult, make_user_filepath


class TestUploadModel:
    """Test Upload Tortoise ORM model."""

    @pytest.mark.asyncio
    async def test_upload_model_creation(self, db):
        """Test Upload model creation succeeds."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="hashed_password_123",
            fingerprint_hash="fp-hash-123",
        )

        upload = await Upload.create(
            user=user,
            description="Test upload",
            name="test_20250124-063307_a1b2c3d4",
            cleanname="test",
            originalname="test.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        assert upload.id is not None
        assert upload.user_id == user.id
        assert upload.description == "Test upload"

    @pytest.mark.asyncio
    async def test_upload_model_all_fields_persist(self, db):
        """Test Upload model persists all required fields."""
        user = await User.create(
            username="testuser2",
            email="test2@example.com",
            password="hashed_password_456",
            fingerprint_hash="fp-hash-456",
        )

        # Create upload with all fields
        original_data = {
            "user": user,
            "description": "Complete test upload",
            "name": "document_20250124-063307_de4c98fa",
            "cleanname": "document",
            "originalname": "My Document.txt",
            "ext": "txt",
            "size": 2048,
            "type": "text/plain",
            "extra": "0",
            "viewed": 5,
            "private": 1,
        }

        upload = await Upload.create(**original_data)

        # Retrieve from database and verify all fields
        retrieved = await Upload.get(id=upload.id)
        assert retrieved.user_id == user.id
        assert retrieved.description == "Complete test upload"
        assert retrieved.name == "document_20250124-063307_de4c98fa"
        assert retrieved.cleanname == "document"
        assert retrieved.originalname == "My Document.txt"
        assert retrieved.ext == "txt"
        assert retrieved.size == 2048
        assert retrieved.type == "text/plain"
        assert retrieved.extra == "0"
        assert retrieved.viewed == 5
        assert retrieved.private == 1

    @pytest.mark.asyncio
    async def test_upload_model_field_defaults(self, db):
        """Test Upload model field defaults."""
        user = await User.create(
            username="testuser3",
            email="test3@example.com",
            password="hashed_password_789",
            fingerprint_hash="fp-hash-789",
        )

        upload = await Upload.create(
            user=user,
            description="",
            name="default_20250124-063307_e5d4c3b2",
            cleanname="default",
            originalname="default.txt",
            ext="txt",
            size=0,
            type="text/plain",
            extra="0",
        )

        # Verify defaults
        assert upload.description == ""
        assert upload.extra == "0"
        assert upload.viewed == 0
        assert upload.private == 0

    @pytest.mark.asyncio
    async def test_upload_model_timestamp_mixin_created_at(self, db):
        """Test Upload model TimestampMixin created_at tracking."""
        user = await User.create(
            username="testuser4",
            email="test4@example.com",
            password="hashed_password_tstamp",
            fingerprint_hash="fp-hash-tstamp",
        )

        before = datetime.now(timezone.utc)
        upload = await Upload.create(
            user=user,
            description="Timestamp test",
            name="timestamp_20250124-063307_f5e6d7c8",
            cleanname="timestamp",
            originalname="timestamp.dat",
            ext="dat",
            size=256,
            type="application/octet-stream",
            extra="0",
        )
        after = datetime.now(timezone.utc)

        # created_at should be between before and after, within reasonable bounds
        assert upload.created_at is not None
        assert before <= upload.created_at <= after + timedelta(seconds=1)

    @pytest.mark.asyncio
    async def test_upload_model_timestamp_mixin_updated_at(self, db):
        """Test Upload model TimestampMixin updated_at tracking."""
        user = await User.create(
            username="testuser5",
            email="test5@example.com",
            password="hashed_password_update",
            fingerprint_hash="fp-hash-update",
        )

        upload = await Upload.create(
            user=user,
            description="Update time test",
            name="updatetime_20250124-063307_b9a8c7d6",
            cleanname="updatetime",
            originalname="updatetime.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        # Both should exist and be close to equal on creation
        assert upload.created_at is not None
        assert upload.updated_at is not None
        # updated_at should be >= created_at
        assert upload.updated_at >= upload.created_at

    @pytest.mark.asyncio
    async def test_upload_model_table_mapping(self, db):
        """Test Upload model maps correctly to uploads table."""
        user = await User.create(
            username="testuser6",
            email="test6@example.com",
            password="hashed_password_table",
            fingerprint_hash="fp-hash-table",
        )

        upload = await Upload.create(
            user=user,
            description="Table mapping test",
            name="mapped_20250124-063307_c1d2e3f4",
            cleanname="mapped",
            originalname="mapped.txt",
            ext="txt",
            size=1024,
            type="text/plain",
            extra="0",
        )

        # Verify we can retrieve by querying all
        all_uploads = await Upload.all()
        assert len(all_uploads) > 0
        assert any(u.id == upload.id for u in all_uploads)

    @pytest.mark.asyncio
    async def test_upload_model_user_relationship(self, db):
        """Test Upload model user relationship."""
        user = await User.create(
            username="testuser7",
            email="test7@example.com",
            password="hashed_password_rel",
            fingerprint_hash="fp-hash-rel",
        )

        upload = await Upload.create(
            user=user,
            description="User relationship test",
            name="related_20250124-063307_c7b6a5d4",
            cleanname="related",
            originalname="related.txt",
            ext="txt",
            size=256,
            type="text/plain",
            extra="0",
        )

        # Verify foreign key relationship works
        retrieved_upload = await Upload.get(id=upload.id)
        assert retrieved_upload.user_id == user.id


class TestUploadMetadata:
    """Test UploadMetadata Pydantic model."""

    def test_uploadmetadata_valid_creation(self):
        """Test UploadMetadata valid creation."""
        metadata = UploadMetadata(
            user_id=1,
            filename="document_20250124-063307_de4c98fa",
            ext="txt",
            original_filename="My Document.txt",
            clean_filename="document",
            size=1024,
            mime_type="text/plain",
        )

        assert metadata.user_id == 1
        assert metadata.filename == "document_20250124-063307_de4c98fa"
        assert metadata.ext == "txt"
        assert metadata.size == 1024

    def test_uploadmetadata_filename_pattern_validation(self):
        """Test UploadMetadata filename pattern validation."""
        # Valid filename patterns
        valid_filenames = [
            "test_20250124-063307_de4c98fa",
            "document_20240101-000000_abcd1234",
            "a_20250124-235959_ffffffff",
            "verylongname_20250124-063307_a1b2c3d4",
        ]

        for filename in valid_filenames:
            metadata = UploadMetadata(
                user_id=1,
                filename=filename,
                ext="txt",
                original_filename="test.txt",
                clean_filename=filename.split("_")[0],
                size=100,
                mime_type="text/plain",
            )
            assert metadata.filename == filename

        # Invalid filename patterns
        invalid_filenames = [
            "document",  # Missing timestamp and UUID
            "document_20250124",  # Missing separator and UUID
            "document_20250124-063307",  # Missing UUID
            "document_20250124-063307_de4c98",  # UUID too short (7 chars)
            "document_20250124-063307_de4c98fag",  # UUID has non-hex char
            "DOCUMENT_20250124-063307_de4c98fa",  # Uppercase not allowed
            "doc-ument_20250124-063307_de4c98fa",  # Dash in name not allowed
        ]

        for invalid_filename in invalid_filenames:
            with pytest.raises(ValidationError):
                UploadMetadata(
                    user_id=1,
                    filename=invalid_filename,
                    ext="txt",
                    original_filename="test.txt",
                    clean_filename="test",
                    size=100,
                    mime_type="text/plain",
                )

    def test_uploadmetadata_ext_validation(self):
        """Test UploadMetadata extension validation."""
        valid_extensions = ["txt", "pdf", "jpg", "png", "gif", "webp", "tar.gz", "tar.bz2"]

        for ext in valid_extensions:
            metadata = UploadMetadata(
                user_id=1,
                filename="test_20250124-063307_abcd1234",
                ext=ext.lower(),
                original_filename="test.txt",
                clean_filename="test",
                size=100,
                mime_type="text/plain",
            )
            assert metadata.ext == ext.lower()

    def test_uploadmetadata_ext_optional(self):
        """Test UploadMetadata extension is optional."""
        metadata = UploadMetadata(
            user_id=1,
            filename="test_20250124-063307_abcd1234",
            ext=None,
            original_filename="test",
            clean_filename="test",
            size=100,
            mime_type="text/plain",
        )
        assert metadata.ext is None

    def test_uploadmetadata_mime_type_validation(self):
        """Test UploadMetadata MIME type validation."""
        # Valid MIME types
        valid_mime_types = [
            "text/plain",
            "image/jpeg",
            "application/pdf",
            "image/png",
            "text/html",
        ]

        for mime_type in valid_mime_types:
            metadata = UploadMetadata(
                user_id=1,
                filename="test_20250124-063307_abcd1234",
                ext="txt",
                original_filename="test.txt",
                clean_filename="test",
                size=100,
                mime_type=mime_type,
            )
            assert metadata.mime_type == mime_type

        # Invalid MIME types
        invalid_mime_types = [
            "invalid",  # Missing /
            "text",  # Missing /
            "/plain",  # Missing type
            "text/",  # Missing subtype
            "text//plain",  # Double slash
        ]

        for invalid_mime in invalid_mime_types:
            with pytest.raises(ValidationError):
                UploadMetadata(
                    user_id=1,
                    filename="test_20250124-063307_abcd1234",
                    ext="txt",
                    original_filename="test.txt",
                    clean_filename="test",
                    size=100,
                    mime_type=invalid_mime,
                )

    def test_uploadmetadata_clean_filename_pattern(self):
        """Test UploadMetadata clean filename pattern validation."""
        valid_clean_names = [
            "a",
            "test",
            "my_document",
            "file_with_underscores",
            "test123",
        ]

        for clean_name in valid_clean_names:
            metadata = UploadMetadata(
                user_id=1,
                filename="test_20250124-063307_abcd1234",
                ext="txt",
                original_filename=f"{clean_name}.txt",
                clean_filename=clean_name,
                size=100,
                mime_type="text/plain",
            )
            assert metadata.clean_filename == clean_name

    def test_uploadmetadata_filepath_property(self):
        """Test UploadMetadata filepath property."""
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
        # Filepath now includes extension
        assert str(filepath).endswith("user_42/test_20250124-063307_abcd1234.txt")

    def test_uploadmetadata_size_positive_integer(self):
        """Test UploadMetadata size validation."""
        metadata = UploadMetadata(
            user_id=1,
            filename="test_20250124-063307_abcd1234",
            ext="txt",
            original_filename="test.txt",
            clean_filename="test",
            size=0,  # Zero is valid
            mime_type="text/plain",
        )
        assert metadata.size == 0

        metadata = UploadMetadata(
            user_id=1,
            filename="test_20250124-063307_abcd1234",
            ext="txt",
            original_filename="test.txt",
            clean_filename="test",
            size=1000000,  # 1MB
            mime_type="text/plain",
        )
        assert metadata.size == 1000000


class TestUploadResult:
    """Test UploadResult Pydantic model."""

    def test_uploadresult_success_structure(self):
        """Test UploadResult success status structure."""
        result = UploadResult(
            status="success",
            message="File uploaded successfully",
            upload_id=None,
            metadata=None,
        )

        assert result.status == "success"
        assert result.message == "File uploaded successfully"
        assert result.upload_id is None
        assert result.metadata is None

    def test_uploadresult_error_structure(self):
        """Test UploadResult error status structure."""
        result = UploadResult(
            status="error",
            message="File size exceeds quota",
            upload_id=None,
            metadata=None,
        )

        assert result.status == "error"
        assert result.message == "File size exceeds quota"
        assert result.upload_id is None
        assert result.metadata is None

    def test_uploadresult_pending_structure(self):
        """Test UploadResult pending status structure."""
        result = UploadResult(
            status="pending",
            message="Upload in progress",
            upload_id=None,
            metadata=None,
        )

        assert result.status == "pending"
        assert result.message == "Upload in progress"
        assert result.upload_id is None
        assert result.metadata is None

    def test_uploadresult_arbitrary_types_allowed(self):
        """Test UploadResult model structure with upload_id field."""
        result = UploadResult(
            status="success",
            message="File uploaded",
            upload_id=None,
            metadata=None,
        )

        assert result.status == "success"
        assert result.message == "File uploaded"
        # Verify upload_id field is present and accepts None
        assert result.upload_id is None


class TestUploadModelIntegration:
    """Integration tests for Upload model with relationships."""

    @pytest.mark.asyncio
    async def test_upload_multiple_users_separate_storage(self, db):
        """Test uploads from multiple users are separate."""
        user1 = await User.create(
            username="user1",
            email="user1@example.com",
            password="hashed_password_user1",
            fingerprint_hash="fp-hash-user1",
        )
        user2 = await User.create(
            username="user2",
            email="user2@example.com",
            password="hashed_password_user2",
            fingerprint_hash="fp-hash-user2",
        )

        upload1 = await Upload.create(
            user=user1,
            description="Upload for user 1",
            name="file1_20250124-063307_a1a1a1a1",
            cleanname="file1",
            originalname="file1.txt",
            ext="txt",
            size=1024,
            type="text/plain",
            extra="0",
        )

        upload2 = await Upload.create(
            user=user2,
            description="Upload for user 2",
            name="file2_20250124-063307_b2b2b2b2",
            cleanname="file2",
            originalname="file2.txt",
            ext="txt",
            size=2048,
            type="text/plain",
            extra="0",
        )

        # Verify they're separate
        assert upload1.user_id != upload2.user_id
        assert upload1.name != upload2.name

    @pytest.mark.asyncio
    async def test_single_user_multiple_uploads(self, db):
        """Test a single user can have multiple uploads."""
        user = await User.create(
            username="multiupload",
            email="multi@example.com",
            password="hashed_password_multi",
            fingerprint_hash="fp-hash-multi",
        )

        # Create multiple uploads
        for i in range(5):
            await Upload.create(
                user=user,
                description=f"Upload {i+1}",
                name=f"file{i+1}_20250124-063307_{str(i)*8}",
                cleanname=f"file{i+1}",
                originalname=f"file{i+1}.txt",
                ext="txt",
                size=512 * (i + 1),
                type="text/plain",
                extra="0",
            )

        # Verify all belong to same user
        uploads = await Upload.filter(user=user)
        assert len(uploads) == 5
        assert all(u.user_id == user.id for u in uploads)


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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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
    """Test Upload model url and static_url properties."""

    @pytest.mark.asyncio
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

        # Expected format: /get/{id}/{cleanname}.{ext}
        expected_url = f"/get/{upload.id}/testfile.txt"
        assert upload.url == expected_url

    @pytest.mark.asyncio
    async def test_upload_static_url_property(self, db):
        """Test Upload static_url property returns correct static file URL."""
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

        # Expected format: /files/user_{id}/{name}.{ext}
        expected_url = f"/files/user_{user.id}/image_20250124-063307_12345678.jpg"
        assert upload.static_url == expected_url

        # Verify url exists (basic check, implementation may vary)
        assert upload.url is not None


    @pytest.mark.asyncio
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
        assert upload.url == f"/get/{upload.id}/README"
        assert upload.static_url == f"/files/user_{user.id}/README_20250124-063307_abcdef12"


class TestUploadDotExtProperty:
    """Test Upload model dot_ext property."""

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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

    @pytest.mark.asyncio
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


class TestUploadPagination:
    """Test Upload model pagination functionality (PaginationMixin)."""

    @pytest.mark.asyncio
    async def test_paginate_returns_queryset(self, db):
        """Test paginate method returns a filtered queryset."""
        user = await User.create(username="pageuser", email="page@example.com", is_registered=True, password="password")
        
        # Create 15 uploads
        for i in range(15):
             await Upload.create(
                user=user,
                description=f"File {i}",
                name=f"file{i}_20250101-000000_12345678",
                cleanname=f"file{i}",
                originalname=f"file{i}.txt",
                ext="txt",
                size=100,
                type="text/plain",
                extra=""
            )

        # Paginate: page 1, size 10
        page1 = await Upload.paginate(page=1, page_size=10, user=user)
        assert len(page1) == 10
        
        # Paginate: page 2, size 10
        page2 = await Upload.paginate(page=2, page_size=10, user=user)
        assert len(page2) == 5

    @pytest.mark.asyncio
    async def test_pages_calculation(self, db):
        """Test pages calculation method."""
        user = await User.create(username="pagecalc", email="calc@example.com", is_registered=True, password="password")
        
        # Create 25 uploads
        for i in range(25):
             await Upload.create(
                user=user,
                description=f"File {i}",
                name=f"file{i}",
                cleanname="file",
                originalname="file.txt",
                ext="txt",
                size=100,
                type="text/plain",
                extra=""
            )
            
        # Page size 10 -> 3 pages
        pages = await Upload.pages(page_size=10, user=user)
        assert pages == 3
        
        # Page size 5 -> 5 pages
        pages = await Upload.pages(page_size=5, user=user)
        assert pages == 5
        
        # Page size 100 -> 1 page
        pages = await Upload.pages(page_size=100, user=user)
        assert pages == 1

    @pytest.mark.asyncio
    async def test_pagination_sorting(self, db):
        """Test pagination sorting arguments."""
        user = await User.create(username="pagesort", email="sort@example.com", is_registered=True, password="password")
        
        # Create 3 uploads with different sizes
        u1 = await Upload.create(user=user, description="Sort test", name="small", cleanname="small", originalname="s.txt", ext="txt", size=10, type="text/plain", extra="")
        u2 = await Upload.create(user=user, description="Sort test", name="medium", cleanname="medium", originalname="m.txt", ext="txt", size=20, type="text/plain", extra="")
        u3 = await Upload.create(user=user, description="Sort test", name="large", cleanname="large", originalname="l.txt", ext="txt", size=30, type="text/plain", extra="")
        
        # Sort by size asc
        asc = await Upload.paginate(page=1, page_size=10, sort_by="size", sort_order="asc", user=user)
        assert asc[0].id == u1.id
        assert asc[2].id == u3.id
        
        # Sort by size desc
        desc = await Upload.paginate(page=1, page_size=10, sort_by="size", sort_order="desc", user=user)
        assert desc[0].id == u3.id
        assert desc[2].id == u1.id
