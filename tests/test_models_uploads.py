"""
Tests for Upload, UploadMetadata, and UploadResult models.

Validates:
- Upload model creation and persistence
- UploadMetadata Pydantic validation (filename pattern, MIME type)
- UploadResult structure for API responses
- Model table mapping and field defaults
- TimestampMixin functionality
"""
import pytest
from datetime import datetime, timezone, timedelta
from pathlib import Path
from pydantic import ValidationError

from app.models.users import User
from app.models.uploads import Upload, UploadMetadata, UploadResult


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
        assert str(filepath).endswith("user_42/test_20250124-063307_abcd1234")

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
            upload=None,
            metadata=None,
        )

        assert result.status == "success"
        assert result.message == "File uploaded successfully"
        assert result.upload is None
        assert result.metadata is None

    def test_uploadresult_error_structure(self):
        """Test UploadResult error status structure."""
        result = UploadResult(
            status="error",
            message="File size exceeds quota",
            upload=None,
            metadata=None,
        )

        assert result.status == "error"
        assert result.message == "File size exceeds quota"
        assert result.upload is None
        assert result.metadata is None

    def test_uploadresult_pending_structure(self):
        """Test UploadResult pending status structure."""
        result = UploadResult(
            status="pending",
            message="Upload in progress",
            upload=None,
            metadata=None,
        )

        assert result.status == "pending"
        assert result.message == "Upload in progress"
        assert result.upload is None
        assert result.metadata is None

    def test_uploadresult_arbitrary_types_allowed(self):
        """Test UploadResult model config allows arbitrary types."""
        result = UploadResult(
            status="success",
            message="File uploaded",
            upload=None,
            metadata=None,
        )

        assert result.status == "success"
        assert result.message == "File uploaded"
        # Verify model_config enables arbitrary_types_allowed
        assert UploadResult.model_config.get("arbitrary_types_allowed") is True


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
