"""Tests for token cleanup scheduler.

Verifies that the scheduled cleanup task correctly removes expired tokens
while preserving valid ones, and that it can be run manually for testing.

Acceptance Criteria:
- Cleanup deletes expired tokens
- Cleanup deletes old revoked tokens (optional)
- Cleanup preserves valid tokens
- Cleanup preserves recently revoked tokens
- Cleanup returns correct count
- Cleanup can be run manually
"""

import hashlib
import uuid
from datetime import datetime, timedelta, timezone
from unittest.mock import patch

import pytest
import pytest_asyncio

from app.lib.scheduler import (
    cleanup_tokens_job as cleanup_tokens_job,
    cleanup_abandoned_users_job as cleanup_abandoned_users_job,
    cleanup_archives_job,
    run_archive_job,
)
from app.models.download_archives import ArchiveFormatsEnum, ArchiveStatusEnum, DownloadArchive
from app.models.uploads import Upload
from app.models.users import User
from app.models.refresh_tokens import RefreshToken


@pytest.fixture(scope="function")
def ensure_scheduler_jobs():
    """Ensure scheduler jobs are registered for integration tests.
    
    The scheduler may be shut down by app lifecycle tests, so we need
    to ensure jobs are re-registered before integration tests run.
    """
    from app.lib.scheduler import scheduler
    
    # If no jobs exist (scheduler was shut down), add them back
    existing_jobs = scheduler.get_jobs()
    existing_job_names = [job.func.__name__ for job in existing_jobs]
    
    if "cleanup_tokens" not in existing_job_names:
        scheduler.add_job(cleanup_tokens_job, 'cron', hour='*', minute=0, jitter=300)
    
    if "cleanup_abandoned_users" not in existing_job_names:
        scheduler.add_job(cleanup_abandoned_users_job, 'cron', hour='*', minute=0, jitter=300)
    
    yield
    
    # Cleanup is handled by app shutdown, no need to do it here


@pytest.fixture(scope="function")
async def test_user(db):
    """Create a test user for scheduler tests."""
    user = await User.create(
        username="scheduser",
        email="sched@example.com",
        password="dummy_hash",
        remember_token=""
    )
    yield user
    await user.delete()


class TestCleanupTokensFunction:
    """Test cleanup_tokens_job() function."""

    @pytest.mark.asyncio
    async def test_cleanup_deletes_expired_tokens(self, test_user):
        """Test that cleanup deletes expired tokens."""
        # Create expired token
        expired_hash = hashlib.sha256("expired_token".encode()).hexdigest()
        expired_token = await RefreshToken.create(
            user=test_user,
            token_hash=expired_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            revoked=False
        )
        
        # Create valid token
        valid_hash = hashlib.sha256("valid_token".encode()).hexdigest()
        valid_token = await RefreshToken.create(
            user=test_user,
            token_hash=valid_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked=False
        )
        
        # Run cleanup
        await cleanup_tokens_job()
        
        # Verify expired token is deleted
        found_expired = await RefreshToken.get_or_none(id=expired_token.id)
        assert found_expired is None
        
        # Verify valid token still exists
        found_valid = await RefreshToken.get_or_none(id=valid_token.id)
        assert found_valid is not None
        
        await valid_token.delete()

    @pytest.mark.asyncio
    async def test_cleanup_preserves_valid_tokens(self, test_user):
        """Test that cleanup preserves valid non-revoked tokens."""
        # Create multiple valid tokens
        valid_tokens = []
        for i in range(3):
            token_hash = hashlib.sha256(f"valid_token_{i}".encode()).hexdigest()
            token = await RefreshToken.create(
                user=test_user,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) + timedelta(days=7),
                revoked=False
            )
            valid_tokens.append(token)
        
        # Run cleanup
        await cleanup_tokens_job()
        
        # Verify all valid tokens still exist
        for token in valid_tokens:
            found = await RefreshToken.get_or_none(id=token.id)
            assert found is not None
        
        # Cleanup
        for token in valid_tokens:
            await token.delete()

    @pytest.mark.asyncio
    async def test_cleanup_with_mixed_tokens(self, test_user):
        """Test cleanup with mix of expired, valid, and revoked tokens."""
        # Create expired token
        expired_hash = hashlib.sha256("expired".encode()).hexdigest()
        expired = await RefreshToken.create(
            user=test_user,
            token_hash=expired_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            revoked=False
        )
        
        # Create valid token
        valid_hash = hashlib.sha256("valid".encode()).hexdigest()
        valid = await RefreshToken.create(
            user=test_user,
            token_hash=valid_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked=False
        )
        
        # Create revoked but not expired token
        revoked_hash = hashlib.sha256("revoked".encode()).hexdigest()
        revoked = await RefreshToken.create(
            user=test_user,
            token_hash=revoked_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked=True
        )
        
        # Run cleanup
        await cleanup_tokens_job()
        
        # Verify expired is deleted
        assert await RefreshToken.get_or_none(id=expired.id) is None
        
        # Verify valid is preserved
        assert await RefreshToken.get_or_none(id=valid.id) is not None
        
        # Verify revoked is preserved (not old enough)
        assert await RefreshToken.get_or_none(id=revoked.id) is not None
        
        # Cleanup
        await valid.delete()
        await revoked.delete()

    @pytest.mark.asyncio
    async def test_cleanup_with_no_tokens(self, test_user):
        """Test that cleanup works when no tokens exist."""
        # Ensure no tokens for user
        await RefreshToken.filter(user=test_user).delete()
        
        # Run cleanup (should not error)
        await cleanup_tokens_job()
        
        # Should complete without error
        count = await RefreshToken.filter(user=test_user).count()
        assert count == 0

    @pytest.mark.asyncio
    async def test_cleanup_multiple_expired_tokens(self, test_user):
        """Test that cleanup deletes multiple expired tokens."""
        # Create multiple expired tokens
        expired_tokens = []
        for i in range(5):
            token_hash = hashlib.sha256(f"expired_{i}".encode()).hexdigest()
            token = await RefreshToken.create(
                user=test_user,
                token_hash=token_hash,
                expires_at=datetime.now(timezone.utc) - timedelta(days=i+1),
                revoked=False
            )
            expired_tokens.append(token)
        
        # Run cleanup
        await cleanup_tokens_job()
        
        # Verify all expired tokens are deleted
        for token in expired_tokens:
            found = await RefreshToken.get_or_none(id=token.id)
            assert found is None

    @pytest.mark.asyncio
    async def test_cleanup_can_be_run_manually(self, test_user):
        """Test that cleanup_tokens_job() can be called manually (not just scheduled)."""
        # Create expired token
        token_hash = hashlib.sha256("manual_test".encode()).hexdigest()
        expired = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            revoked=False
        )
        
        # Call cleanup directly
        await cleanup_tokens_job()
        
        # Verify token was cleaned up
        found = await RefreshToken.get_or_none(id=expired.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_cleanup_with_exactly_expired_token(self, test_user):
        """Test cleanup with token that just expired."""
        # Create token that expired 1 second ago
        token_hash = hashlib.sha256("just_expired".encode()).hexdigest()
        just_expired = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(seconds=1),
            revoked=False
        )
        
        # Run cleanup
        await cleanup_tokens_job()
        
        # Should be deleted
        found = await RefreshToken.get_or_none(id=just_expired.id)
        assert found is None

    @pytest.mark.asyncio
    async def test_cleanup_with_token_expiring_soon(self, test_user):
        """Test that cleanup preserves tokens expiring soon but not yet expired."""
        # Create token expiring in 1 second
        token_hash = hashlib.sha256("expiring_soon".encode()).hexdigest()
        expiring_soon = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(seconds=1),
            revoked=False
        )
        
        # Run cleanup
        await cleanup_tokens_job()
        
        # Should NOT be deleted
        found = await RefreshToken.get_or_none(id=expiring_soon.id)
        assert found is not None
        
        await expiring_soon.delete()


class TestSchedulerIntegration:
    """Test scheduler integration (if scheduler is running)."""

    @pytest.mark.asyncio
    async def test_scheduler_exists(self):
        """Test that scheduler module exists and is importable."""
        from app.lib.scheduler import scheduler, cleanup_tokens_job
        
        assert scheduler is not None
        assert callable(cleanup_tokens_job)

    def test_cleanup_job_scheduled(self, ensure_scheduler_jobs):
        """Test that cleanup job is scheduled in the scheduler."""
        from app.lib.scheduler import scheduler
        
        # Ensure jobs are registered (fixture handles this)
        # Check if scheduler has jobs
        jobs = scheduler.get_jobs()
        assert len(jobs) > 0
        
        # Check if cleanup_tokens is scheduled
        job_funcs = [job.func.__name__ for job in jobs]
        assert "cleanup_tokens_job" in job_funcs


# ============================================================================
# run_archive_job
# ============================================================================

class TestRunArchiveJob:

    @pytest_asyncio.fixture
    async def user(self, db):
        return await User.create(
            username="archivejobuser",
            email="archivejob@example.com",
            password="hashed_password",
            fingerprint_hash="fp-archivejob",
        )

    @pytest_asyncio.fixture
    async def upload(self, user):
        return await Upload.create(
            user=user,
            name="file_20260328-000000_abcd1234.jpg",
            cleanname="file",
            originalname="file.jpg",
            ext="jpg",
            size=100,
            type="image/jpeg",
            extra="",
            description="",
        )

    @pytest_asyncio.fixture
    async def archive(self, user, upload):
        return await DownloadArchive.create(
            user=user,
            upload_ids=[upload.id],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.pending,
            filename="archive_archivejobuser_20260328-000000_abcd1234.zip",
        )

    @pytest.mark.asyncio
    async def test_success_transitions_to_ready(self, archive, tmp_path):
        """Successful archive creation transitions status pending → ready."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        def fake_create_archive():
            (archive_dir / archive.filename).write_bytes(b"dummy archive data")

        with patch("app.lib.scheduler.config") as mock_config, \
             patch("app.lib.scheduler.FileArchive") as MockFileArchive:
            mock_config.archive_storage_path = archive_dir
            MockFileArchive.return_value.create_archive.side_effect = fake_create_archive

            await run_archive_job(archive.id)

        refreshed = await DownloadArchive.get(id=archive.id)
        assert refreshed.status == ArchiveStatusEnum.ready

    @pytest.mark.asyncio
    async def test_success_archive_file_exists(self, archive, tmp_path):
        """Successful archive creation leaves the file on disk."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        def fake_create_archive():
            (archive_dir / archive.filename).write_bytes(b"dummy archive data")

        with patch("app.lib.scheduler.config") as mock_config, \
             patch("app.lib.scheduler.FileArchive") as MockFileArchive:
            mock_config.archive_storage_path = archive_dir
            MockFileArchive.return_value.create_archive.side_effect = fake_create_archive

            await run_archive_job(archive.id)

        assert (archive_dir / archive.filename).exists()

    @pytest.mark.asyncio
    async def test_create_archive_raises_sets_failed(self, archive, tmp_path):
        """If create_archive raises, status transitions to failed."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        with patch("app.lib.scheduler.config") as mock_config, \
             patch("app.lib.scheduler.FileArchive") as MockFileArchive:
            mock_config.archive_storage_path = archive_dir
            MockFileArchive.return_value.create_archive.side_effect = RuntimeError("disk full")

            await run_archive_job(archive.id)

        refreshed = await DownloadArchive.get(id=archive.id)
        assert refreshed.status == ArchiveStatusEnum.failed

    @pytest.mark.asyncio
    async def test_create_archive_raises_logs_error(self, archive, tmp_path):
        """If create_archive raises, the error is logged."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        with patch("app.lib.scheduler.config") as mock_config, \
             patch("app.lib.scheduler.FileArchive") as MockFileArchive, \
             patch("app.lib.scheduler.logger") as mock_logger:
            mock_config.archive_storage_path = archive_dir
            MockFileArchive.return_value.create_archive.side_effect = RuntimeError("disk full")

            await run_archive_job(archive.id)

        mock_logger.error.assert_called_once()
        assert "disk full" in mock_logger.error.call_args[0][0]

    @pytest.mark.asyncio
    async def test_archive_not_found_returns_early(self, db, tmp_path):
        """Non-existent archive ID logs and returns without raising."""
        with patch("app.lib.scheduler.FileArchive") as MockFileArchive, \
             patch("app.lib.scheduler.logger"):
            await run_archive_job(uuid.uuid4())
            MockFileArchive.assert_not_called()

    @pytest.mark.asyncio
    async def test_non_pending_archive_is_skipped(self, archive, tmp_path):
        """Archive already in processing state is not picked up by the job."""
        archive.status = ArchiveStatusEnum.processing
        await archive.save()

        with patch("app.lib.scheduler.FileArchive") as MockFileArchive:
            await run_archive_job(archive.id)
            MockFileArchive.assert_not_called()

        refreshed = await DownloadArchive.get(id=archive.id)
        assert refreshed.status == ArchiveStatusEnum.processing

    @pytest.mark.asyncio
    async def test_missing_upload_sets_failed(self, user, db):
        """Archive referencing an upload that no longer exists transitions to failed."""
        archive = await DownloadArchive.create(
            user=user,
            upload_ids=[99999],
            format=ArchiveFormatsEnum.zip,
            status=ArchiveStatusEnum.pending,
            filename="archive_archivejobuser_20260328-000000_deadbeef.zip",
        )

        with patch("app.lib.scheduler.FileArchive") as MockFileArchive:
            await run_archive_job(archive.id)
            MockFileArchive.assert_not_called()

        refreshed = await DownloadArchive.get(id=archive.id)
        assert refreshed.status == ArchiveStatusEnum.failed

    @pytest.mark.asyncio
    async def test_empty_archive_file_sets_failed(self, archive, tmp_path):
        """If create_archive writes an empty file, status transitions to failed."""
        archive_dir = tmp_path / "archives"
        archive_dir.mkdir()

        def fake_create_empty():
            (archive_dir / archive.filename).write_bytes(b"")

        with patch("app.lib.scheduler.config") as mock_config, \
             patch("app.lib.scheduler.FileArchive") as MockFileArchive:
            mock_config.archive_storage_path = archive_dir
            MockFileArchive.return_value.create_archive.side_effect = fake_create_empty

            await run_archive_job(archive.id)

        refreshed = await DownloadArchive.get(id=archive.id)
        assert refreshed.status == ArchiveStatusEnum.failed


# ============================================================================
# cleanup_archives_job
# ============================================================================

class TestCleanupArchivesJob:

    @pytest.mark.asyncio
    async def test_calls_cleanup_expired(self, db):
        """cleanup_archives_job calls DownloadArchive.cleanup_expired."""
        with patch("app.lib.scheduler.DownloadArchive.cleanup_expired", return_value=0) as mock_expired, \
             patch("app.lib.scheduler.cleanup_orphaned_archives", return_value=0):
            await cleanup_archives_job()
            mock_expired.assert_called_once()

    @pytest.mark.asyncio
    async def test_calls_cleanup_orphaned_archives(self, db):
        """cleanup_archives_job calls cleanup_orphaned_archives."""
        with patch("app.lib.scheduler.DownloadArchive.cleanup_expired", return_value=0), \
             patch("app.lib.scheduler.cleanup_orphaned_archives", return_value=0) as mock_orphans:
            await cleanup_archives_job()
            mock_orphans.assert_called_once()

    @pytest.mark.asyncio
    async def test_logs_expired_count(self, db):
        """cleanup_archives_job logs the number of expired archives removed."""
        with patch("app.lib.scheduler.DownloadArchive.cleanup_expired", return_value=3), \
             patch("app.lib.scheduler.cleanup_orphaned_archives", return_value=0), \
             patch("app.lib.scheduler.logger") as mock_logger:
            await cleanup_archives_job()

        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("3" in msg for msg in log_messages)

    @pytest.mark.asyncio
    async def test_logs_orphan_count(self, db):
        """cleanup_archives_job logs the number of orphaned files removed."""
        with patch("app.lib.scheduler.DownloadArchive.cleanup_expired", return_value=0), \
             patch("app.lib.scheduler.cleanup_orphaned_archives", return_value=2), \
             patch("app.lib.scheduler.logger") as mock_logger:
            await cleanup_archives_job()

        log_messages = [call[0][0] for call in mock_logger.info.call_args_list]
        assert any("2" in msg for msg in log_messages)
