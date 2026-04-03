"""Tests for user authentication and unregistered user management in app/lib/auth.py.

- get_current_user_from_request validates access tokens from request cookies
- authenticate_user verifies credentials by username or email
- get_or_create_unregistered_user creates or retrieves unregistered users by fingerprint
- get_unregistered_user_by_fingerprint looks up unregistered users without side-effects
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock
from fastapi import Request

from app.lib.config import get_app_config
from app.lib.auth import (
    create_access_token,
    get_current_user_from_request,
    get_or_create_unregistered_user,
    get_unregistered_user_by_fingerprint,
)
from app.models.users import User, authenticate_user


class TestGetCurrentUserFromRequest:
    """Test get_current_user_from_request() dependency function."""

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
        mock_request.state.user = None  # Ensure we test cookie path, not middleware-injected user

        user = await get_current_user_from_request(mock_request)

        assert user == mock_user

    async def test_without_token(self):
        """Test that missing token returns None."""
        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        mock_request.state.user = None

        user = await get_current_user_from_request(mock_request)

        assert user is None

    async def test_with_invalid_token(self):
        """Test that invalid token returns None."""
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": "invalid_token"}
        mock_request.state.user = None

        user = await get_current_user_from_request(mock_request)

        assert user is None

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
        mock_request.state.user = None

        user = await get_current_user_from_request(mock_request)

        assert user is None

    async def test_with_nonexistent_user(self, monkeypatch):
        """Test that token for nonexistent user returns anonymous user."""
        token = create_access_token(data={"sub": "nonexistent"})

        # Mock User.get_or_none to return None
        async def mock_get_or_none(**kwargs):
            return None

        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)

        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": token}
        mock_request.state.user = None

        user = await get_current_user_from_request(mock_request)

        assert user is None


class TestAuthenticateUser:
    """Test authenticate_user() function."""

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

    async def test_nonexistent_user(self, monkeypatch):
        """Test that nonexistent user returns None."""
        async def mock_get_or_none(**kwargs):
            return None

        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)

        user = await authenticate_user(username="nonexistent", password="password")

        assert user is None


class TestGetOrCreateUnregisteredUser:
    """Test get_or_create_unregistered_user() function."""

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
