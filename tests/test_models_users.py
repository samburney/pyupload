"""Tests for RefreshToken model.

Verifies that the RefreshToken model correctly stores and manages refresh tokens
with proper relationships to User model and database constraints.

Acceptance Criteria:
- RefreshToken instances can be created with all required fields
- Foreign key relationship to User model works correctly
- Token hash is stored correctly
- Expires_at datetime handling works properly
- Revoked flag defaults to False
- Database constraints are enforced
- Model methods work as expected
"""

import pytest
import hashlib
from datetime import datetime, timedelta, timezone

from app.models.users import User, RefreshToken


@pytest.fixture(scope="function")
async def test_user(db):
    """Create a test user for refresh token tests."""
    user = await User.create(
        username="testuser",
        email="test@example.com",
        password="dummy_hash",
        remember_token=""
    )
    yield user
    await user.delete()


class TestRefreshTokenModel:
    """Test RefreshToken model creation and fields."""

    @pytest.mark.asyncio
    async def test_create_refresh_token(self, test_user):
        """Test that RefreshToken instance can be created successfully."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False
        )

        assert refresh_token.id is not None
        assert refresh_token.user_id == test_user.id
        assert refresh_token.token_hash == token_hash
        assert refresh_token.expires_at == expires_at
        assert refresh_token.revoked is False

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_refresh_token_foreign_key_relationship(self, test_user):
        """Test that foreign key relationship to User works."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at
        )

        # Fetch the relationship
        await refresh_token.fetch_related("user")
        assert refresh_token.user.id == test_user.id
        assert refresh_token.user.username == test_user.username

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_refresh_token_hash_stored_correctly(self, test_user):
        """Test that token_hash is stored correctly."""
        original_token = "my_secret_token_12345"
        token_hash = hashlib.sha256(original_token.encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at
        )

        # Verify hash is stored correctly
        assert refresh_token.token_hash == token_hash
        assert len(refresh_token.token_hash) == 64  # SHA256 hex is 64 chars

        # Verify we can query by hash
        found = await RefreshToken.get_or_none(token_hash=token_hash)
        assert found is not None
        assert found.id == refresh_token.id

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_refresh_token_expires_at_datetime(self, test_user):
        """Test that expires_at datetime is handled correctly."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at
        )

        # Verify expires_at is stored correctly
        assert refresh_token.expires_at is not None
        assert isinstance(refresh_token.expires_at, datetime)
        
        # Should be in the future
        assert refresh_token.expires_at > datetime.now(timezone.utc)

        # Should be approximately 7 days from now (within 1 minute tolerance)
        time_diff = abs((refresh_token.expires_at - expires_at).total_seconds())
        assert time_diff < 60

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_refresh_token_revoked_defaults_to_false(self, test_user):
        """Test that revoked flag defaults to False."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        # Create without specifying revoked
        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at
        )

        assert refresh_token.revoked is False

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_refresh_token_timestamps(self, test_user):
        """Test that created_at and updated_at timestamps work."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at
        )

        # Verify timestamps exist
        assert refresh_token.created_at is not None
        assert refresh_token.updated_at is not None
        assert isinstance(refresh_token.created_at, datetime)
        assert isinstance(refresh_token.updated_at, datetime)

        # Both should be recent (within last minute)
        now = datetime.now(timezone.utc)
        assert (now - refresh_token.created_at).total_seconds() < 60
        assert (now - refresh_token.updated_at).total_seconds() < 60

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_refresh_token_cascade_delete_with_user(self, test_user):
        """Test that deleting user cascades to refresh tokens."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at
        )

        token_id = refresh_token.id

        # Delete the user
        await test_user.delete()

        # Token should be deleted too (cascade)
        found = await RefreshToken.get_or_none(id=token_id)
        assert found is None

    @pytest.mark.asyncio
    async def test_multiple_refresh_tokens_per_user(self, db):
        """Test that a user can have multiple refresh tokens."""
        user = await User.create(
            username="multitoken_user",
            email="multi@example.com",
            password="dummy_hash",
            remember_token=""
        )

        # Create multiple tokens
        tokens = []
        for i in range(3):
            token_hash = hashlib.sha256(f"token_{i}".encode()).hexdigest()
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            token = await RefreshToken.create(
                user=user,
                token_hash=token_hash,
                expires_at=expires_at
            )
            tokens.append(token)

        # Verify all tokens exist
        user_tokens = await RefreshToken.filter(user=user)
        assert len(user_tokens) == 3

        # Cleanup
        await user.delete()


class TestRefreshTokenMethods:
    """Test RefreshToken model methods."""

    @pytest.mark.asyncio
    async def test_revoke_method(self, test_user):
        """Test RefreshToken.revoke() instance method."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False
        )

        # Revoke the token
        result = await refresh_token.revoke()

        assert result is True
        assert refresh_token.revoked is True

        # Verify in database
        await refresh_token.refresh_from_db()
        assert refresh_token.revoked is True

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_revoke_method_idempotent(self, test_user):
        """Test that revoking already-revoked token is idempotent."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=True  # Already revoked
        )

        # Revoke again
        result = await refresh_token.revoke()

        assert result is True
        assert refresh_token.revoked is True

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_is_valid_method_with_valid_token(self, test_user):
        """Test RefreshToken.is_valid() returns True for valid token."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False
        )

        assert refresh_token.is_valid() is True

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_is_valid_method_with_revoked_token(self, test_user):
        """Test RefreshToken.is_valid() returns False for revoked token."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) + timedelta(days=7)

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=True
        )

        assert refresh_token.is_valid() is False

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_is_valid_method_with_expired_token(self, test_user):
        """Test RefreshToken.is_valid() returns False for expired token."""
        token_hash = hashlib.sha256("test_token".encode()).hexdigest()
        expires_at = datetime.now(timezone.utc) - timedelta(days=1)  # Expired yesterday

        refresh_token = await RefreshToken.create(
            user=test_user,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False
        )

        assert refresh_token.is_valid() is False

        await refresh_token.delete()

    @pytest.mark.asyncio
    async def test_revoke_all_for_user_method(self, db):
        """Test RefreshToken.revoke_all_for_user() class method."""
        user = await User.create(
            username="revoke_all_user",
            email="revokeall@example.com",
            password="dummy_hash",
            remember_token=""
        )

        # Create multiple tokens
        for i in range(3):
            token_hash = hashlib.sha256(f"token_{i}".encode()).hexdigest()
            expires_at = datetime.now(timezone.utc) + timedelta(days=7)
            await RefreshToken.create(
                user=user,
                token_hash=token_hash,
                expires_at=expires_at,
                revoked=False
            )

        # Revoke all user tokens
        count = await RefreshToken.revoke_all_for_user(user.id)

        assert count == 3

        # Verify all are revoked
        user_tokens = await RefreshToken.filter(user=user)
        for token in user_tokens:
            assert token.revoked is True

        await user.delete()

    @pytest.mark.asyncio
    async def test_cleanup_expired_method(self, db):
        """Test RefreshToken.cleanup_expired() class method."""
        user = await User.create(
            username="cleanup_user",
            email="cleanup@example.com",
            password="dummy_hash",
            remember_token=""
        )

        # Create expired token
        expired_hash = hashlib.sha256("expired_token".encode()).hexdigest()
        expired_token = await RefreshToken.create(
            user=user,
            token_hash=expired_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            revoked=False
        )

        # Create valid token
        valid_hash = hashlib.sha256("valid_token".encode()).hexdigest()
        valid_token = await RefreshToken.create(
            user=user,
            token_hash=valid_hash,
            expires_at=datetime.now(timezone.utc) + timedelta(days=7),
            revoked=False
        )

        # Run cleanup
        count = await RefreshToken.cleanup_expired()

        assert count >= 1  # At least the expired one

        # Verify expired token is deleted
        found_expired = await RefreshToken.get_or_none(id=expired_token.id)
        assert found_expired is None

        # Verify valid token still exists
        found_valid = await RefreshToken.get_or_none(id=valid_token.id)
        assert found_valid is not None

        await user.delete()
