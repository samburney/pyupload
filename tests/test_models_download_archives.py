"""
Tests for the DownloadArchive model.

Validates:
- Model creation and persistence
- Status and format enum values
- upload_ids JSONField stores list of IDs correctly
- UUID primary key is auto-generated
- TimestampMixin fields are populated
"""
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.models.users import User
from app.models.download_archives import DownloadArchive, ArchiveStatusEnum, ArchiveFormatsEnum


async def _make_user(suffix="") -> User:
    return await User.create(
        username=f"archiveuser{suffix}",
        email=f"archive{suffix}@example.com",
        password="hashed_password",
        fingerprint_hash=f"fp-archive{suffix}",
    )


class TestDownloadArchiveModel:

    @pytest.mark.asyncio
    async def test_create_pending(self, db):
        """Model can be created and persisted with pending status."""
        user = await _make_user()
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[1, 2, 3],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.pending,
            filename="archive_sam_20260327-193717_a1b2c3d4.zip",
        )

        assert archive.id is not None
        assert archive.status == ArchiveStatusEnum.pending
        assert archive.format == ArchiveFormatsEnum.zip
        assert archive.upload_ids == [1, 2, 3]

    @pytest.mark.asyncio
    async def test_defaults(self, db):
        """status defaults to pending and format defaults to zip."""
        user = await _make_user("0")
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            filename="archive_sam_20260327-193717_a1b2c3d4.zip",
        )

        assert archive.status == ArchiveStatusEnum.pending
        assert archive.format == ArchiveFormatsEnum.zip

    @pytest.mark.asyncio
    async def test_uuid_primary_key(self, db):
        """Primary key is a UUID auto-generated on creation."""
        user = await _make_user("2")
        a1 = await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.pending,
            filename="archive_testuser_20260327-193717_a1b2c3d4.zip",
        )
        a2 = await DownloadArchive.create(
            user=user,
            upload_ids=[2],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.pending,
            filename="archive_testuser_20260327-193717_a1b2c3d4.zip",
        )

        assert a1.id != a2.id
        assert str(a1.id)  # serialises to a string

    @pytest.mark.asyncio
    async def test_upload_ids_roundtrip(self, db):
        """upload_ids JSONField persists and retrieves a list of integers correctly."""
        user = await _make_user("3")
        ids = [10, 20, 99, 1000]
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=ids,
            format=ArchiveFormatsEnum.tar_gzip,
            status=ArchiveStatusEnum.pending,
            filename="archive_testuser_20260327-193717_a1b2c3d4.zip",
        )

        fetched = await DownloadArchive.get(id=archive.id)
        assert fetched.upload_ids == ids

    @pytest.mark.asyncio
    async def test_status_transitions(self, db):
        """Status field can be updated through the lifecycle."""
        user = await _make_user("4")
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[5],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.pending,
            filename="archive_testuser_20260327-193717_a1b2c3d4.zip",
        )

        archive.status = ArchiveStatusEnum.processing
        await archive.save()

        archive.status = ArchiveStatusEnum.ready
        archive.filename = "archives/test.zip"
        await archive.save()

        fetched = await DownloadArchive.get(id=archive.id)
        assert fetched.status == ArchiveStatusEnum.ready
        assert fetched.filename == "archives/test.zip"

    @pytest.mark.asyncio
    async def test_all_formats_accepted(self, db):
        """All canonical format enum values can be persisted."""
        user = await _make_user("5")
        for fmt in (ArchiveFormatsEnum.zip, ArchiveFormatsEnum.tar_gzip, ArchiveFormatsEnum.tar_zstd):
            archive = await DownloadArchive.create(
                user=user,
                upload_ids=[1],
                format=fmt,
                status=ArchiveStatusEnum.pending,
                filename="archive_testuser_20260327-193717_a1b2c3d4.zip",
            )
            fetched = await DownloadArchive.get(id=archive.id)
            assert fetched.format == fmt

    @pytest.mark.asyncio
    async def test_timestamp_mixin_populated(self, db):
        """created_at and updated_at are set on creation."""
        user = await _make_user("6")
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.pending,
            filename="archive_testuser_20260327-193717_a1b2c3d4.zip",
        )

        assert archive.created_at is not None
        assert archive.updated_at is not None

    @pytest.mark.asyncio
    async def test_user_cascade_delete(self, db):
        """Deleting a user cascades to their DownloadArchive records."""
        user = await _make_user("7")
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.pending,
            filename="archive_testuser_20260327-193717_a1b2c3d4.zip",
        )
        archive_id = archive.id

        await user.delete()

        assert await DownloadArchive.get_or_none(id=archive_id) is None


# ============================================================================
# DownloadArchive.cleanup_expired
# ============================================================================

class TestDownloadArchiveCleanupExpired:

    @pytest_asyncio.fixture
    async def user(self, db):
        return await User.create(
            username="expireduser",
            email="expired@example.com",
            password="hashed_password",
            fingerprint_hash="fp-expired",
        )

    async def _make_expired_archive(self, user, suffix="") -> DownloadArchive:
        """Create a DownloadArchive with created_at backdated past the 24h TTL."""
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.ready,
            filename=f"archive_expired_20260328-000000_exp0{suffix}.zip",
        )
        past = datetime.now(timezone.utc) - timedelta(hours=25)
        await DownloadArchive.filter(id=archive.id).update(created_at=past)
        return await DownloadArchive.get(id=archive.id)

    @pytest.mark.asyncio
    async def test_deletes_expired_db_records(self, user):
        """Expired archive records are removed from the database."""
        archive = await self._make_expired_archive(user)

        with patch("app.models.download_archives.config") as mock_config:
            mock_config.archive_max_age_hours = 24
            mock_config.archive_storage_path = Path("/nonexistent_path_for_test")
            await DownloadArchive.cleanup_expired()

        assert await DownloadArchive.get_or_none(id=archive.id) is None

    @pytest.mark.asyncio
    async def test_preserves_non_expired_records(self, user):
        """Recently created archive records are not deleted."""
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.ready,
            filename="archive_fresh_20260328-000000_fresh001.zip",
        )

        with patch("app.models.download_archives.config") as mock_config:
            mock_config.archive_max_age_hours = 24
            mock_config.archive_storage_path = Path("/nonexistent_path_for_test")
            count = await DownloadArchive.cleanup_expired()

        assert await DownloadArchive.get_or_none(id=archive.id) is not None
        assert count == 0
        await DownloadArchive.filter(id=archive.id).delete()

    @pytest.mark.asyncio
    async def test_deletes_archive_file_from_disk(self, user, tmp_path):
        """cleanup_expired removes the archive file from disk."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()
        filename = "archive_expired_20260328-000000_disktest.zip"
        (archive_dir / filename).write_bytes(b"dummy archive")

        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.ready,
            filename=filename,
        )
        past = datetime.now(timezone.utc) - timedelta(hours=25)
        await DownloadArchive.filter(id=archive.id).update(created_at=past)

        with patch("app.models.download_archives.config") as mock_config:
            mock_config.archive_max_age_hours = 24
            mock_config.archive_storage_path = archive_dir
            await DownloadArchive.cleanup_expired()

        assert not (archive_dir / filename).exists()

    @pytest.mark.asyncio
    async def test_returns_count_of_deleted_records(self, user):
        """cleanup_expired returns the number of records deleted."""
        for i in range(3):
            await self._make_expired_archive(user, suffix=str(i))

        with patch("app.models.download_archives.config") as mock_config:
            mock_config.archive_max_age_hours = 24
            mock_config.archive_storage_path = Path("/nonexistent_path_for_test")
            count = await DownloadArchive.cleanup_expired()

        assert count == 3

    @pytest.mark.asyncio
    async def test_mixed_expired_and_fresh(self, user):
        """Only expired records are deleted; fresh records are preserved."""
        expired = await self._make_expired_archive(user, suffix="mix")
        fresh = await DownloadArchive.create(
            user=user,
            upload_ids=[1],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.ready,
            filename="archive_fresh_20260328-000000_mixfresh.zip",
        )

        with patch("app.models.download_archives.config") as mock_config:
            mock_config.archive_max_age_hours = 24
            mock_config.archive_storage_path = Path("/nonexistent_path_for_test")
            count = await DownloadArchive.cleanup_expired()

        assert count == 1
        assert await DownloadArchive.get_or_none(id=expired.id) is None
        assert await DownloadArchive.get_or_none(id=fresh.id) is not None
        await DownloadArchive.filter(id=fresh.id).delete()
