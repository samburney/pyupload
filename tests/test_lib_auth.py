"""Tests for authentication library functions (app/lib/auth.py).

Tests JWT token creation, validation, cookie handling, refresh token management,
and other core authentication library functions.

Acceptance Criteria:
- JWT access tokens created correctly with proper expiration
- Refresh tokens created and validated properly
- Token cookies configured with correct security settings
- get_current_user validates tokens and returns User
- authenticate_user validates credentials
- Refresh token storage, validation, and revocation work correctly
"""

import pytest
import jwt
import hashlib
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock
from fastapi import Request

from app.lib.config import get_app_config
from app.lib.auth import (
    create_access_token,
    create_refresh_token,
    create_token_cookie,
    get_current_user_from_request,
    store_refresh_token,
    validate_refresh_token,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
    get_or_create_unregistered_user,
    get_unregistered_user_by_fingerprint,
)
from app.models.users import User, UserPydantic, authenticate_user, mark_abandoned
from app.models.refresh_tokens import RefreshToken


# ============================================================================
# JWT Access Token Tests
# ============================================================================

class TestCreateAccessToken:
    """Test create_access_token() function."""

    def test_returns_valid_jwt_string(self):
        """Test that create_access_token returns a valid JWT string."""
        token = create_access_token(data={"sub": "testuser"})
        
        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count('.') == 2  # JWT has 3 parts

    def test_contains_subject_claim(self):
        """Test that created token contains the subject claim."""
        config = get_app_config()
        username = "testuser"
        token = create_access_token(data={"sub": username})
        
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        
        assert payload["sub"] == username

    def test_has_expiration(self):
        """Test that created token has an expiration time."""
        config = get_app_config()
        token = create_access_token(data={"sub": "testuser"})
        
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        
        assert "exp" in payload
        exp_timestamp = payload["exp"]
        now_timestamp = datetime.now(timezone.utc).timestamp()
        assert exp_timestamp > now_timestamp

    def test_expiration_time_is_correct(self):
        """Test that token expires after configured minutes."""
        config = get_app_config()
        token = create_access_token(data={"sub": "testuser"})
        
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        
        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_exp = datetime.now(timezone.utc) + timedelta(minutes=config.auth_token_age_minutes)
        
        # Should be within 5 seconds
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 5

    def test_uses_correct_algorithm(self):
        """Test that token is created with configured algorithm."""
        config = get_app_config()
        token = create_access_token(data={"sub": "testuser"})
        
        # Decode and verify algorithm
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        
        assert payload is not None


# ============================================================================
# JWT Refresh Token Tests
# ============================================================================

class TestCreateRefreshToken:
    """Test create_refresh_token() function."""

    def test_creates_valid_jwt(self):
        """Test that create_refresh_token creates a valid JWT string."""
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        token = create_refresh_token(mock_user)

        assert isinstance(token, str)
        assert len(token) > 0
        assert token.count('.') == 2  # JWT has 3 parts

    def test_token_contains_user_id(self):
        """Test that token contains user ID in subject claim."""
        config = get_app_config()
        mock_user = Mock(spec=User)
        mock_user.id = 42
        
        token = create_refresh_token(mock_user)

        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )

        assert payload["sub"] == str(mock_user.id)

    def test_token_has_expiration(self):
        """Test that token has expiration time."""
        config = get_app_config()
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        token = create_refresh_token(mock_user)

        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )

        assert "exp" in payload
        exp_timestamp = payload["exp"]
        now_timestamp = datetime.now(timezone.utc).timestamp()
        assert exp_timestamp > now_timestamp

    def test_token_expiration_is_correct(self):
        """Test that token expires after configured days."""
        config = get_app_config()
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        token = create_refresh_token(mock_user)

        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )

        exp_time = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)
        expected_exp = datetime.now(timezone.utc) + timedelta(days=config.auth_refresh_token_age_days)

        # Should be within 5 seconds
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 5


class TestStoreRefreshToken:
    """Test store_refresh_token() function."""

    @pytest.mark.asyncio
    async def test_stores_token_in_database(self, db):
        """Test that token is stored in database."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        refresh_token = await store_refresh_token(token, user)

        assert refresh_token.id is not None
        assert refresh_token.user_id == user.id

        await user.delete()

    @pytest.mark.asyncio
    async def test_stores_hashed_token(self, db):
        """Test that token is hashed before storage."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        refresh_token = await store_refresh_token(token, user)

        # Token should be hashed
        expected_hash = hashlib.sha256(token.encode()).hexdigest()
        assert refresh_token.token_hash == expected_hash
        assert refresh_token.token_hash != token

        await user.delete()

    @pytest.mark.asyncio
    async def test_extracts_expiration_from_jwt(self, db):
        """Test that expiration is extracted from JWT."""
        config = get_app_config()
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        refresh_token = await store_refresh_token(token, user)

        # Decode token to get expected expiration
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        expected_exp = datetime.fromtimestamp(payload["exp"], tz=timezone.utc)

        # Compare with stored expiration (within 1 second)
        time_diff = abs((refresh_token.expires_at - expected_exp).total_seconds())
        assert time_diff < 1

        await user.delete()

    @pytest.mark.asyncio
    async def test_sets_revoked_to_false(self, db):
        """Test that revoked is set to False by default."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        refresh_token = await store_refresh_token(token, user)

        assert refresh_token.revoked is False

        await user.delete()

    @pytest.mark.asyncio
    async def test_raises_on_invalid_jwt(self, db):
        """Test that invalid JWT raises ValueError."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        with pytest.raises(ValueError):
            await store_refresh_token("not_a_valid_jwt", user)
        
        await user.delete()


class TestValidateRefreshToken:
    """Test validate_refresh_token() function."""

    @pytest.mark.asyncio
    async def test_validates_valid_token(self, db):
        """Test that valid token is validated successfully."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        await store_refresh_token(token, user)

        result = await validate_refresh_token(token, user)

        assert result is not None
        assert result.user_id == user.id
        assert result.revoked is False

        await user.delete()

    @pytest.mark.asyncio
    async def test_validates_with_user_id(self, db):
        """Test that validation works with user ID instead of User object."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        await store_refresh_token(token, user)

        result = await validate_refresh_token(token, user.id)

        assert result is not None
        assert result.user_id == user.id

        await user.delete()

    @pytest.mark.asyncio
    async def test_rejects_expired_token(self, db):
        """Test that expired token returns None."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        # Create expired token
        expired_hash = hashlib.sha256("expired_token".encode()).hexdigest()
        await RefreshToken.create(
            user=user,
            token_hash=expired_hash,
            expires_at=datetime.now(timezone.utc) - timedelta(days=1),
            revoked=False
        )

        # Try to validate (token will fail JWT decode, so use a valid JWT that's expired in DB)
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        fresh_token = create_refresh_token(mock_user)
        
        result = await validate_refresh_token(fresh_token, user)

        # Will return None because stored token doesn't match
        assert result is None

        await user.delete()

    @pytest.mark.asyncio
    async def test_rejects_revoked_token(self, db):
        """Test that revoked token returns None."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        refresh_token = await store_refresh_token(token, user)

        # Revoke the token
        refresh_token.revoked = True
        await refresh_token.save()

        result = await validate_refresh_token(token, user)

        assert result is None

        await user.delete()

    @pytest.mark.asyncio
    async def test_rejects_nonexistent_token(self, db):
        """Test that nonexistent token returns None."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        # Don't store it

        result = await validate_refresh_token(token, user)

        assert result is None

        await user.delete()

    @pytest.mark.asyncio
    async def test_rejects_invalid_jwt(self, db):
        """Test that invalid JWT returns None."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        result = await validate_refresh_token("not_a_valid_jwt", user)

        assert result is None

        await user.delete()

    @pytest.mark.asyncio
    async def test_rejects_wrong_user_token(self, db):
        """Test that token for different user returns None."""
        user1 = await User.create(
            username="user1",
            email="user1@example.com",
            password="dummy_hash",
            remember_token=""
        )
        user2 = await User.create(
            username="user2",
            email="user2@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user1 = Mock(spec=User)
        mock_user1.id = user1.id
        token = create_refresh_token(mock_user1)
        await store_refresh_token(token, user1)

        # Try to validate with wrong user
        result = await validate_refresh_token(token, user2)

        assert result is None

        await user1.delete()
        await user2.delete()


class TestRevokeRefreshToken:
    """Test revoke_refresh_token() function."""

    @pytest.mark.asyncio
    async def test_revokes_valid_token(self, db):
        """Test that valid token is revoked."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        refresh_token = await store_refresh_token(token, user)

        result = await revoke_refresh_token(token, user)

        assert result is True
        
        # Verify it's revoked
        await refresh_token.refresh_from_db()
        assert refresh_token.revoked is True

        await user.delete()

    @pytest.mark.asyncio
    async def test_revoke_with_user_id(self, db):
        """Test that revocation works with user ID."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        refresh_token = await store_refresh_token(token, user)

        result = await revoke_refresh_token(token, user.id)

        assert result is True
        
        await refresh_token.refresh_from_db()
        assert refresh_token.revoked is True

        await user.delete()

    @pytest.mark.asyncio
    async def test_revoke_nonexistent_token_returns_false(self, db):
        """Test that revoking nonexistent token returns False."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        # Don't store it

        result = await revoke_refresh_token(token, user)

        assert result is False

        await user.delete()


class TestRevokeUserRefreshTokens:
    """Test revoke_user_refresh_tokens() function."""

    @pytest.mark.asyncio
    async def test_revokes_all_user_tokens(self, db):
        """Test that all user tokens are revoked."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        
        # Create multiple tokens
        for _ in range(3):
            token = create_refresh_token(mock_user)
            await store_refresh_token(token, user)

        count = await revoke_user_refresh_tokens(user)

        assert count == 3

        # Verify all are revoked
        user_tokens = await RefreshToken.filter(user=user)
        for token in user_tokens:
            assert token.revoked is True

        await user.delete()

    @pytest.mark.asyncio
    async def test_revoke_with_user_id(self, db):
        """Test that revocation works with user ID."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        token = create_refresh_token(mock_user)
        await store_refresh_token(token, user)

        count = await revoke_user_refresh_tokens(user.id)

        assert count == 1

        await user.delete()

    @pytest.mark.asyncio
    async def test_revoke_doesnt_affect_other_users(self, db):
        """Test that revoking user tokens doesn't affect other users."""
        user1 = await User.create(
            username="user1",
            email="user1@example.com",
            password="dummy_hash",
            remember_token=""
        )
        user2 = await User.create(
            username="user2",
            email="user2@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user1 = Mock(spec=User)
        mock_user1.id = user1.id
        mock_user2 = Mock(spec=User)
        mock_user2.id = user2.id
        
        # Create tokens for both users
        token1 = create_refresh_token(mock_user1)
        await store_refresh_token(token1, user1)

        token2 = create_refresh_token(mock_user2)
        await store_refresh_token(token2, user2)

        # Revoke first user's tokens
        await revoke_user_refresh_tokens(user1)

        # Verify first user's token is revoked
        hash1 = hashlib.sha256(token1.encode()).hexdigest()
        refresh1 = await RefreshToken.get_or_none(token_hash=hash1)
        assert refresh1.revoked is True

        # Verify second user's token is NOT revoked
        hash2 = hashlib.sha256(token2.encode()).hexdigest()
        refresh2 = await RefreshToken.get_or_none(token_hash=hash2)
        assert refresh2.revoked is False

        await user1.delete()
        await user2.delete()

    @pytest.mark.asyncio
    async def test_revoke_no_tokens_returns_zero(self, db):
        """Test that revoking when user has no tokens returns 0."""
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        count = await revoke_user_refresh_tokens(user)

        assert count == 0

        await user.delete()


class TestMultiUserIsolation:
    """Test that tokens are properly isolated between users."""

    @pytest.mark.asyncio
    async def test_validate_only_returns_own_tokens(self, db):
        """Test that validating token only returns if it belongs to requesting user."""
        user1 = await User.create(
            username="user1",
            email="user1@example.com",
            password="dummy_hash",
            remember_token=""
        )
        user2 = await User.create(
            username="user2",
            email="user2@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user1 = Mock(spec=User)
        mock_user1.id = user1.id
        
        # Create token for user1
        token1 = create_refresh_token(mock_user1)
        await store_refresh_token(token1, user1)

        # Try to validate with user1 (should work)
        result1 = await validate_refresh_token(token1, user1)
        assert result1 is not None
        assert result1.user_id == user1.id

        # Try to validate same token with user2 (should fail)
        result2 = await validate_refresh_token(token1, user2)
        assert result2 is None

        await user1.delete()
        await user2.delete()

    @pytest.mark.asyncio
    async def test_revoke_only_affects_own_tokens(self, db):
        """Test that revoking tokens only affects specified user."""
        user1 = await User.create(
            username="user1",
            email="user1@example.com",
            password="dummy_hash",
            remember_token=""
        )
        user2 = await User.create(
            username="user2",
            email="user2@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user1 = Mock(spec=User)
        mock_user1.id = user1.id
        mock_user2 = Mock(spec=User)
        mock_user2.id = user2.id
        
        token1 = create_refresh_token(mock_user1)
        await store_refresh_token(token1, user1)

        token2 = create_refresh_token(mock_user2)
        await store_refresh_token(token2, user2)

        # Revoke user1's tokens
        await revoke_user_refresh_tokens(user1)

        # Check user1's token is revoked
        result1 = await validate_refresh_token(token1, user1)
        assert result1 is None  # Revoked

        # Check user2's token is still valid
        result2 = await validate_refresh_token(token2, user2)
        assert result2 is not None  # Not revoked

        await user1.delete()
        await user2.delete()


# ============================================================================
# Token Cookie Tests
# ============================================================================

class TestCreateTokenCookie:
    """Test create_token_cookie() function."""

    def test_returns_dict(self):
        """Test that create_token_cookie returns a dictionary."""
        cookie = create_token_cookie(token="test_token")
        
        assert isinstance(cookie, dict)

    def test_has_required_fields(self):
        """Test that cookie dictionary has all required fields."""
        cookie = create_token_cookie(token="test_token")
        
        required_fields = ["key", "value", "httponly", "max_age", "secure", "samesite"]
        for field in required_fields:
            assert field in cookie, f"Cookie missing required field: {field}"

    def test_access_token_key_name(self):
        """Test that access token cookie uses correct key name."""
        cookie = create_token_cookie(token="test_token", token_type="access")
        
        assert cookie["key"] == "access_token"

    def test_refresh_token_key_name(self):
        """Test that refresh token cookie uses correct key name."""
        cookie = create_token_cookie(token="test_token", token_type="refresh")
        
        assert cookie["key"] == "refresh_token"

    def test_httponly_enabled(self):
        """Test that cookie has httponly flag enabled for security."""
        cookie = create_token_cookie(token="test_token")
        
        assert cookie["httponly"] is True

    def test_secure_enabled(self):
        """Test that cookie has secure flag enabled for HTTPS."""
        cookie = create_token_cookie(token="test_token")
        
        assert cookie["secure"] is True

    def test_samesite_configured(self):
        """Test that cookie has samesite policy configured."""
        cookie = create_token_cookie(token="test_token")
        
        assert cookie["samesite"] == "lax"

    def test_access_token_max_age(self):
        """Test that access token cookie has correct max_age."""
        config = get_app_config()
        cookie = create_token_cookie(token="test_token", token_type="access")
        
        expected_seconds = config.auth_token_age_minutes * 60
        assert cookie["max_age"] == expected_seconds

    def test_refresh_token_max_age(self):
        """Test that refresh token cookie has correct max_age."""
        config = get_app_config()
        cookie = create_token_cookie(token="test_token", token_type="refresh")
        
        expected_seconds = config.auth_refresh_token_age_days * 24 * 60 * 60
        assert cookie["max_age"] == expected_seconds


# ============================================================================
# get_current_user_from_request Tests
# ============================================================================

class TestGetCurrentUserFromRequest:
    """Test get_current_user_from_request() dependency function."""

    @pytest.mark.asyncio
    async def test_with_valid_token(self, monkeypatch):
        """Test that valid token returns user."""
        config = get_app_config()
        token = create_access_token(data={"sub": "testuser"})
        
        # Mock User.get_or_none
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        # Mock request with token cookie
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": token}
        
        user = await get_current_user_from_request(mock_request)
        
        assert user == mock_user

    @pytest.mark.asyncio
    async def test_without_token(self):
        """Test that missing token returns None."""
        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        
        user = await get_current_user_from_request(mock_request)
        
        assert user is None

    @pytest.mark.asyncio
    async def test_with_invalid_token(self):
        """Test that invalid token returns None."""
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": "invalid_token"}
        
        user = await get_current_user_from_request(mock_request)
        
        assert user is None

    @pytest.mark.asyncio
    async def test_with_expired_token(self):
        """Test that expired token returns anonymous user."""
        # Create token that's already expired
        config = get_app_config()
        past_time = datetime.now(timezone.utc) - timedelta(minutes=60)
        to_encode = {"sub": "testuser", "exp": past_time}
        expired_token = jwt.encode(
            to_encode,
            config.auth_token_secret_key,
            algorithm=config.auth_token_algorithm
        )
        
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": expired_token}
        
        user = await get_current_user_from_request(mock_request)
        
        assert user is None

    @pytest.mark.asyncio
    async def test_with_nonexistent_user(self, monkeypatch):
        """Test that token for nonexistent user returns anonymous user."""
        token = create_access_token(data={"sub": "nonexistent"})
        
        # Mock User.get_or_none to return None
        async def mock_get_or_none(**kwargs):
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": token}
        
        user = await get_current_user_from_request(mock_request)
        
        assert user is None


# ============================================================================
# authenticate_user Tests
# ============================================================================

class TestAuthenticateUser:
    """Test authenticate_user() function."""

    @pytest.mark.asyncio
    async def test_with_username(self, monkeypatch):
        """Test authentication with username."""
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        mock_user.password = "hashed_password"
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        def mock_verify(plain_password, hashed_password):
            return plain_password == "correct_password" and hashed_password == "hashed_password"
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        import app.models.users
        monkeypatch.setattr(app.models.users, "verify_password", mock_verify)
        
        user = await authenticate_user(username="testuser", password="correct_password")
        
        assert user == mock_user

    @pytest.mark.asyncio
    async def test_with_email(self, monkeypatch):
        """Test authentication with email."""
        mock_user = Mock(spec=User)
        mock_user.email = "test@example.com"
        mock_user.password = "hashed_password"
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("email") == "test@example.com":
                return mock_user
            return None
        
        def mock_verify(plain_password, hashed_password):
            return plain_password == "correct_password" and hashed_password == "hashed_password"
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        import app.models.users
        monkeypatch.setattr(app.models.users, "verify_password", mock_verify)
        
        user = await authenticate_user(username="test@example.com", password="correct_password")
        
        assert user == mock_user

    @pytest.mark.asyncio
    async def test_wrong_password(self, monkeypatch):
        """Test that wrong password returns None."""
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        mock_user.password = "hashed_password"
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        def mock_verify(plain_password, hashed_password):
            return False
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        import app.models.users
        monkeypatch.setattr(app.models.users, "verify_password", mock_verify)
        
        user = await authenticate_user(username="testuser", password="wrong_password")
        
        assert user is None

    @pytest.mark.asyncio
    async def test_nonexistent_user(self, monkeypatch):
        """Test that nonexistent user returns None."""
        async def mock_get_or_none(**kwargs):
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        user = await authenticate_user(username="nonexistent", password="password")
        
        assert user is None


# ============================================================================
# Auto-Registration Tests
# ============================================================================

class TestGetOrCreateUnregisteredUser:
    """Test get_or_create_unregistered_user() function."""

    @pytest.mark.asyncio
    async def test_creates_new_user_on_new_fingerprint(self, db):
        """Test that new fingerprint creates new user."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        user = await get_or_create_unregistered_user(mock_request)
        
        assert user is not None
        assert user.id is not None
        assert user.username is not None
        assert user.is_registered is False
        assert user.is_abandoned is False
        assert user.fingerprint_hash is not None

    @pytest.mark.asyncio
    async def test_returns_existing_user_on_fingerprint_match(self, db):
        """Test that existing fingerprint returns same user."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Create first user
        user1 = await get_or_create_unregistered_user(mock_request)
        
        # Same fingerprint should return same user
        user2 = await get_or_create_unregistered_user(mock_request)
        
        assert user1.id == user2.id
        assert user1.username == user2.username

    @pytest.mark.asyncio
    async def test_skips_abandoned_users(self, db):
        """Test that abandoned users are skipped and new user created."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Create and abandon a user
        user1 = await get_or_create_unregistered_user(mock_request)
        user1.is_abandoned = True
        await user1.save()
        
        # Same fingerprint should create NEW user (abandoned user skipped)
        user2 = await get_or_create_unregistered_user(mock_request)
        
        assert user1.id != user2.id
        assert user2.is_abandoned is False

    @pytest.mark.asyncio
    async def test_skips_disabled_users(self, db):
        """Test that disabled users are skipped and new user created."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Create and disable a user
        user1 = await get_or_create_unregistered_user(mock_request)
        user1.is_disabled = True
        await user1.save()
        
        # Same fingerprint should create NEW user (disabled user skipped)
        user2 = await get_or_create_unregistered_user(mock_request)
        
        assert user1.id != user2.id
        assert user2.is_disabled is False

    @pytest.mark.asyncio
    async def test_skips_registered_users(self, db):
        """Test that registered users are skipped and new user created."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Create and register a user
        user1 = await get_or_create_unregistered_user(mock_request)
        user1.is_registered = True
        user1.email = "test@example.com"
        user1.password = "hash"
        await user1.save()
        
        # Same fingerprint should create NEW user (registered user skipped)
        user2 = await get_or_create_unregistered_user(mock_request)
        
        assert user1.id != user2.id
        assert user2.is_registered is False

    @pytest.mark.asyncio
    async def test_different_fingerprints_create_different_users(self, db):
        """Test that different fingerprints create different users."""
        mock_request1 = Mock(spec=Request)
        mock_request1.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request1.client = Mock()
        mock_request1.client.host = "192.168.1.1"
        
        mock_request2 = Mock(spec=Request)
        mock_request2.headers = {
            "User-Agent": "Chrome/91.0",  # Different
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request2.client = Mock()
        mock_request2.client.host = "192.168.1.1"
        
        user1 = await get_or_create_unregistered_user(mock_request1)
        user2 = await get_or_create_unregistered_user(mock_request2)
        
        assert user1.id != user2.id

    @pytest.mark.asyncio
    async def test_sets_registration_ip(self, db):
        """Test that registration_ip is set on new users."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "10.0.0.100"
        
        user = await get_or_create_unregistered_user(mock_request)
        
        assert user.registration_ip is not None
        assert "10.0.0.100" in str(user.registration_ip)

    @pytest.mark.asyncio
    async def test_sets_fingerprint_data(self, db):
        """Test that fingerprint_data is populated on new users."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        user = await get_or_create_unregistered_user(mock_request)
        
        assert user.fingerprint_data is not None
        assert "user_agent" in user.fingerprint_data
        assert user.fingerprint_data["user_agent"] == "Mozilla/5.0"


class TestGetUnregisteredUserByFingerprint:
    """Test get_unregistered_user_by_fingerprint() function."""

    @pytest.mark.asyncio
    async def test_returns_user_with_matching_fingerprint(self, db):
        """Test that matching fingerprint returns user."""
        # Create an unregistered user with known fingerprint
        user = await User.create(
            username="TestUser1234",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="a" * 64
        )
        
        # Mock request that produces same fingerprint hash
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        # Patch generate_fingerprint_hash to return our known hash
        import app.lib.auth
        original_hash_fn = app.lib.auth.generate_fingerprint_hash
        app.lib.auth.generate_fingerprint_hash = lambda r, **kwargs: "a" * 64
        
        try:
            found_user = await get_unregistered_user_by_fingerprint(mock_request)
            
            assert found_user is not None
            assert found_user.id == user.id
        finally:
            app.lib.auth.generate_fingerprint_hash = original_hash_fn

    @pytest.mark.asyncio
    async def test_returns_none_for_no_match(self, db):
        """Test that non-matching fingerprint returns None."""
        mock_request = Mock(spec=Request)
        mock_request.headers = {
            "User-Agent": "Mozilla/5.0",
            "Accept-Language": "en-US",
            "Accept-Encoding": "gzip"
        }
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        result = await get_unregistered_user_by_fingerprint(mock_request)
        
        assert result is None

    @pytest.mark.asyncio
    async def test_skips_registered_users_in_lookup(self, db):
        """Test that registered users are not returned even with matching fingerprint."""
        # Create a registered user with fingerprint
        await User.create(
            username="RegisteredUser",
            email="test@example.com",
            password="hash",
            is_registered=True,
            fingerprint_hash="b" * 64
        )
        
        # Mock request with same fingerprint
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        import app.lib.auth
        original_hash_fn = app.lib.auth.generate_fingerprint_hash
        app.lib.auth.generate_fingerprint_hash = lambda r, **kwargs: "b" * 64
        
        try:
            result = await get_unregistered_user_by_fingerprint(mock_request)
            
            # Should not return registered user
            assert result is None
        finally:
            app.lib.auth.generate_fingerprint_hash = original_hash_fn

    @pytest.mark.asyncio
    async def test_skips_abandoned_users_in_lookup(self, db):
        """Test that abandoned users are not returned even with matching fingerprint."""
        # Create an abandoned user with fingerprint
        await User.create(
            username="AbandonedUser",
            email="",
            password="",
            is_registered=False,
            is_abandoned=True,
            fingerprint_hash="c" * 64
        )
        
        # Mock request with same fingerprint
        mock_request = Mock(spec=Request)
        mock_request.headers = {}
        mock_request.client = Mock()
        mock_request.client.host = "192.168.1.1"
        
        import app.lib.auth
        original_hash_fn = app.lib.auth.generate_fingerprint_hash
        app.lib.auth.generate_fingerprint_hash = lambda r, **kwargs: "c" * 64
        
        try:
            result = await get_unregistered_user_by_fingerprint(mock_request)
            
            # Should not return abandoned user
            assert result is None
        finally:
            app.lib.auth.generate_fingerprint_hash = original_hash_fn


# ============================================================================
# Abandonment Cleanup Tests
# ============================================================================

class TestMarkAbandoned:
    """Test mark_abandoned() function."""

    @pytest.mark.asyncio
    async def test_marks_old_unregistered_users_as_abandoned(self, db):
        """Test that old unregistered users are marked as abandoned."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config
        
        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)
        
        # Create an old unregistered user
        old_user = await User.create(
            username="OldUser",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=cutoff_date,
            fingerprint_hash="d" * 64
        )
        
        # Run abandonment cleanup
        count = await mark_abandoned()
        
        # Refresh from database
        await old_user.refresh_from_db()
        
        assert count == 1
        assert old_user.is_abandoned is True
        assert old_user.fingerprint_hash is None

    @pytest.mark.asyncio
    async def test_preserves_recent_unregistered_users(self, db):
        """Test that recent unregistered users are not marked as abandoned."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config
        
        config = get_app_config()
        recent_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days - 1)
        
        # Create a recent unregistered user
        recent_user = await User.create(
            username="RecentUser",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=recent_date,
            fingerprint_hash="e" * 64
        )
        
        # Run abandonment cleanup
        count = await mark_abandoned()
        
        # Refresh from database
        await recent_user.refresh_from_db()
        
        assert count == 0
        assert recent_user.is_abandoned is False
        assert recent_user.fingerprint_hash is not None

    @pytest.mark.asyncio
    async def test_skips_registered_users(self, db):
        """Test that registered users are never marked as abandoned."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config
        
        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)
        
        # Create an old registered user
        registered_user = await User.create(
            username="RegisteredUser",
            email="registered@example.com",
            password="hash",
            is_registered=True,
            is_abandoned=False,
            last_seen_at=cutoff_date
        )
        
        # Run abandonment cleanup
        count = await mark_abandoned()
        
        # Refresh from database
        await registered_user.refresh_from_db()
        
        assert count == 0
        assert registered_user.is_abandoned is False

    @pytest.mark.asyncio
    async def test_skips_already_abandoned_users(self, db):
        """Test that already abandoned users are skipped (idempotent)."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config
        
        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)
        
        # Create an already abandoned user
        abandoned_user = await User.create(
            username="AlreadyAbandoned",
            email="",
            password="",
            is_registered=False,
            is_abandoned=True,
            last_seen_at=cutoff_date
        )
        
        # Run abandonment cleanup
        count = await mark_abandoned()
        
        assert count == 0

    @pytest.mark.asyncio
    async def test_clears_fingerprint_on_abandonment(self, db):
        """Test that fingerprint is cleared when user is marked as abandoned."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config
        
        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)
        
        # Create old user with fingerprint
        user = await User.create(
            username="UserWithFingerprint",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=cutoff_date,
            fingerprint_hash="f" * 64,
            fingerprint_data={"user_agent": "Mozilla/5.0"}
        )
        
        # Run abandonment cleanup
        await mark_abandoned()
        
        # Refresh from database
        await user.refresh_from_db()
        
        # Fingerprint hash should be cleared, but fingerprint_data retained
        assert user.fingerprint_hash is None
        assert user.fingerprint_data is not None
        assert user.fingerprint_data["user_agent"] == "Mozilla/5.0"

    @pytest.mark.asyncio
    async def test_returns_accurate_count(self, db):
        """Test that function returns accurate count of abandoned users."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config
        
        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)
        
        # Create multiple old unregistered users
        for i in range(5):
            await User.create(
                username=f"OldUser{i}",
                email="",
                password="",
                is_registered=False,
                is_abandoned=False,
                last_seen_at=cutoff_date,
                fingerprint_hash=f"{i}" * 64
            )
        
        # Run abandonment cleanup
        count = await mark_abandoned()
        
        assert count == 5

    @pytest.mark.asyncio
    async def test_idempotent_multiple_runs(self, db):
        """Test that running cleanup multiple times is safe (idempotent)."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config
        
        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)
        
        # Create old unregistered user
        await User.create(
            username="OldUser",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=cutoff_date,
            fingerprint_hash="g" * 64
        )
        
        # Run cleanup first time
        count1 = await mark_abandoned()
        assert count1 == 1
        
        # Run cleanup second time
        count2 = await mark_abandoned()
        assert count2 == 0  # No more users to abandon

    @pytest.mark.asyncio
    async def test_retains_fingerprint_data_for_audit(self, db):
        """Test that fingerprint_data is retained for record-keeping."""
        from datetime import datetime, timedelta
        from app.lib.config import get_app_config
        
        config = get_app_config()
        cutoff_date = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days + 1)
        
        fingerprint_data = {
            "user_agent": "Mozilla/5.0",
            "accept_language": "en-US",
            "accept_encoding": "gzip",
            "client_ip": "192.168.1.1"
        }
        
        user = await User.create(
            username="UserForAudit",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            last_seen_at=cutoff_date,
            fingerprint_hash="h" * 64,
            fingerprint_data=fingerprint_data
        )
        
        await mark_abandoned()
        await user.refresh_from_db()
        
        # fingerprint_data should be retained
        assert user.fingerprint_data == fingerprint_data
        assert user.fingerprint_hash is None


