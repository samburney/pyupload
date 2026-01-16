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

import pytest
from datetime import datetime, timedelta, timezone

from app.lib.scheduler import cleanup_tokens
from app.models.users import User, RefreshToken
import hashlib


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
    """Test cleanup_tokens() function."""

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
        await cleanup_tokens()
        
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
        await cleanup_tokens()
        
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
        await cleanup_tokens()
        
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
        await cleanup_tokens()
        
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
        await cleanup_tokens()
        
        # Verify all expired tokens are deleted
        for token in expired_tokens:
            found = await RefreshToken.get_or_none(id=token.id)
            assert found is None

    @pytest.mark.asyncio
    async def test_cleanup_can_be_run_manually(self, test_user):
        """Test that cleanup_tokens() can be called manually (not just scheduled)."""
        # Create expired token
        token_hash = hashlib.sha256("manual_test".encode()).hexdigest()
        expired = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(hours=1),
            revoked=False
        )
        
        # Call cleanup directly
        await cleanup_tokens()
        
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
        await cleanup_tokens()
        
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
        await cleanup_tokens()
        
        # Should NOT be deleted
        found = await RefreshToken.get_or_none(id=expiring_soon.id)
        assert found is not None
        
        await expiring_soon.delete()


class TestSchedulerIntegration:
    """Test scheduler integration (if scheduler is running)."""

    @pytest.mark.asyncio
    async def test_scheduler_exists(self):
        """Test that scheduler module exists and is importable."""
        from app.lib.scheduler import scheduler, cleanup_tokens
        
        assert scheduler is not None
        assert callable(cleanup_tokens)

    def test_cleanup_job_scheduled(self):
        """Test that cleanup job is scheduled in the scheduler."""
        from app.lib.scheduler import scheduler
        
        # Check if scheduler has jobs
        jobs = scheduler.get_jobs()
        assert len(jobs) > 0
        
        # Check if cleanup_tokens is scheduled
        job_funcs = [job.func.__name__ for job in jobs]
        assert "cleanup_tokens" in job_funcs
