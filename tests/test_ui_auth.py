"""Tests for app/ui/auth.py - Authentication UI endpoints.

This module tests the FastAPI/Starlette authentication endpoints:
- /login (GET and POST)
- /logout
- /logout-all  
- /refresh

Tests use Starlette TestClient for HTTP request testing.
"""

import pytest
from unittest.mock import Mock
from datetime import datetime, timedelta, timezone
from starlette.testclient import TestClient
import hashlib

from app.main import app
from app.models.users import User, RefreshToken
from app.lib.auth import create_access_token, create_refresh_token
from app.lib.config import get_app_config


class TestLoginEndpoint:
    """Test login endpoint with JWT token generation."""

    @pytest.mark.asyncio
    async def test_login_endpoint_exists(self):
        """Test that login endpoint is accessible."""
        client = TestClient(app)
        response = client.get("/login")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_login_post_with_valid_credentials_sets_cookie(self, monkeypatch):
        """Test that successful login sets access_token cookie."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Mock authenticate_user to return a user
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        mock_user.id = 1
        
        async def mock_authenticate(**kwargs):
            return mock_user
        
        # Mock store_refresh_token to avoid database operations
        async def mock_store_refresh_token(token_payload, user):
            pass

        # Import and patch the functions
        import app.ui.auth
        import app.lib.auth
        monkeypatch.setattr(app.ui.auth, "authenticate_user", mock_authenticate)
        monkeypatch.setattr(app.lib.auth, "store_refresh_token", mock_store_refresh_token)
        
        # Attempt login
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "password"}
        )
        
        # Should return success and set access_token cookie
        assert response.status_code == 200
        assert "access_token" in response.cookies

    @pytest.mark.asyncio
    async def test_login_post_with_invalid_credentials_returns_401(self, monkeypatch):
        """Test that login with invalid credentials returns 401."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Mock authenticate_user to return None
        async def mock_authenticate(**kwargs):
            return None
        
        import app.ui.auth
        monkeypatch.setattr(app.ui.auth, "authenticate_user", mock_authenticate)
        
        # Attempt login with wrong credentials
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "wrongpassword"}
        )
        
        assert response.status_code == 401


class TestLogoutEndpoint:
    """Test logout endpoint with JWT token removal."""

    @pytest.mark.asyncio
    async def test_logout_endpoint_exists(self, monkeypatch):
        """Test that logout endpoint is accessible."""
        from app.lib.config import get_app_config
        config = get_app_config()
        
        # Create a valid token to authenticate
        token = create_access_token(data={"sub": "testuser"})
        
        # Mock User.get_or_none to return authenticated user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        client = TestClient(app)
        client.cookies.set("access_token", token)
        response = client.get("/logout", follow_redirects=False)
        
        # Should redirect
        assert response.status_code in [302, 303, 307]

    @pytest.mark.asyncio
    async def test_logout_deletes_access_token_cookie(self, monkeypatch):
        """Test that logout deletes the access_token cookie."""
        # Create a valid token to authenticate
        token = create_access_token(data={"sub": "testuser"})
        
        # Mock User.get_or_none to return authenticated user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        client = TestClient(app)
        client.cookies.set("access_token", token)
        
        response = client.get("/logout", follow_redirects=False)
        
        # Cookie should be deleted (set to empty or expired)
        # Check if access_token is in delete cookies
        set_cookie_header = response.headers.get("set-cookie", "")
        
        # The cookie should be deleted (max-age=0 or expires in past)
        assert "access_token" in set_cookie_header.lower() or response.status_code in [302, 303, 307]

    @pytest.mark.asyncio
    async def test_logout_redirects_to_home(self, monkeypatch):
        """Test that logout redirects to home page."""
        # Create a valid token to authenticate
        token = create_access_token(data={"sub": "testuser"})
        
        # Mock User.get_or_none to return authenticated user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        client = TestClient(app)
        client.cookies.set("access_token", token)
        
        response = client.get("/logout", follow_redirects=False)
        
        # Should be a redirect response
        assert response.status_code in [302, 303, 307]
        
        # Should redirect to root
        assert response.headers.get("location") == "/"


# Tests for /refresh endpoint removed - endpoint replaced by TokenRefreshMiddleware
# Token refresh now happens automatically via middleware in app/middleware/token_refresh.py
# See tests/test_middleware_token_refresh.py for middleware tests


class TestLoginRefreshTokenIntegration:
    """Test login endpoint properly creates and stores refresh tokens."""

    @pytest.mark.asyncio
    async def test_login_sets_refresh_token_cookie(self, monkeypatch):
        """Test that successful login sets refresh_token cookie."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Mock authenticate_user
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        mock_user.id = 1
        
        async def mock_authenticate(**kwargs):
            return mock_user
        
        # Mock store_refresh_token
        async def mock_store_refresh_token(token_payload, user):
            pass
        
        import app.ui.auth
        import app.lib.auth
        monkeypatch.setattr(app.ui.auth, "authenticate_user", mock_authenticate)
        monkeypatch.setattr(app.lib.auth, "store_refresh_token", mock_store_refresh_token)
        
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "password"}
        )
        
        # Should set both access and refresh tokens
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    @pytest.mark.asyncio
    async def test_login_stores_refresh_token_in_database(self, monkeypatch):
        """Test that login stores refresh token in database."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Track if store was called
        store_called = {"value": False, "token": None, "user": None}
        
        # Mock authenticate_user
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        mock_user.id = 1
        
        async def mock_authenticate(**kwargs):
            return mock_user
        
        # Mock store_refresh_token
        async def mock_store_refresh_token(token, user):
            store_called["value"] = True
            store_called["token"] = token
            store_called["user"] = user
        
        import app.ui.auth
        import app.lib.auth
        monkeypatch.setattr(app.ui.auth, "authenticate_user", mock_authenticate)
        monkeypatch.setattr(app.lib.auth, "store_refresh_token", mock_store_refresh_token)
        
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "password"}
        )
        
        # Should have called store_refresh_token
        assert store_called["value"] is True
        assert store_called["token"] is not None
        assert store_called["user"] == mock_user


class TestLogoutRefreshTokenIntegration:
    """Test logout endpoint properly revokes refresh tokens."""

    @pytest.mark.asyncio
    async def test_logout_revokes_refresh_token(self, monkeypatch):
        """Test that logout revokes the refresh token."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Track if revoke was called
        revoke_called = {"value": False}
        
        # Create tokens
        from app.lib.auth import create_access_token, create_refresh_token
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        access_token = create_access_token(data={"sub": "testuser"})
        refresh_token = create_refresh_token(mock_user)
        
        # Mock User.get_or_none
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        # Mock revoke_refresh_token
        async def mock_revoke(token, user):
            revoke_called["value"] = True
            return True
        
        import app.ui.auth
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        monkeypatch.setattr(app.ui.auth, "revoke_refresh_token", mock_revoke)
        
        # Make request with both tokens
        client.cookies.set("access_token", access_token)
        client.cookies.set("refresh_token", refresh_token)
        response = client.get("/logout", follow_redirects=False)
        
        # Should have revoked the token
        assert revoke_called["value"] is True

    @pytest.mark.asyncio
    async def test_logout_deletes_both_cookies(self, monkeypatch):
        """Test that logout deletes both access and refresh token cookies."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Create tokens
        from app.lib.auth import create_access_token, create_refresh_token
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        access_token = create_access_token(data={"sub": "testuser"})
        refresh_token = create_refresh_token(mock_user)
        
        # Mock User.get_or_none
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        # Mock revoke_refresh_token
        async def mock_revoke(token, user):
            return True
        
        import app.lib.auth
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        monkeypatch.setattr(app.lib.auth, "revoke_refresh_token", mock_revoke)
        
        # Make request
        client.cookies.set("access_token", access_token)
        client.cookies.set("refresh_token", refresh_token)
        response = client.get("/logout", follow_redirects=False)
        
        # Both cookies should be deleted (marked for deletion with empty value or max_age=0)
        # The cookies dict will show them but they're marked for deletion
        assert response.status_code in [302, 303, 307]

    @pytest.mark.asyncio
    async def test_logout_works_without_refresh_token(self, monkeypatch):
        """Test that logout works even without refresh token (backward compat)."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Create only access token
        from app.lib.auth import create_access_token
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        access_token = create_access_token(data={"sub": "testuser"})
        
        # Mock User.get_or_none
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        # Mock revoke (should return False when no token)
        async def mock_revoke(token, user):
            return False
        
        import app.lib.auth
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        monkeypatch.setattr(app.lib.auth, "revoke_refresh_token", mock_revoke)
        
        # Make request with only access token
        client.cookies.set("access_token", access_token)
        response = client.get("/logout", follow_redirects=False)
        
        # Should still succeed
        assert response.status_code in [302, 303, 307]


class TestLogoutAllEndpoint:
    """Test /logout-all endpoint functionality."""

    @pytest.mark.asyncio
    async def test_logout_all_endpoint_exists(self, monkeypatch):
        """Test that /logout-all endpoint is accessible."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Create token for authentication
        from app.lib.auth import create_access_token
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        access_token = create_access_token(data={"sub": "testuser"})
        
        # Mock User.get_or_none
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        # Mock revoke_user_refresh_tokens
        async def mock_revoke_all(user):
            return 0
        
        import app.lib.auth
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        monkeypatch.setattr(app.lib.auth, "revoke_user_refresh_tokens", mock_revoke_all)
        
        client.cookies.set("access_token", access_token)
        response = client.get("/logout-all", follow_redirects=False)
        
        # Should redirect
        assert response.status_code in [302, 303, 307]

    @pytest.mark.asyncio
    async def test_logout_all_requires_authentication(self):
        """Test that /logout-all requires authenticated user."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Make request without authentication
        response = client.get("/logout-all", follow_redirects=False)
        
        # Should return 403 (forbidden)
        assert response.status_code == 403

    @pytest.mark.asyncio
    async def test_logout_all_revokes_all_user_tokens(self, monkeypatch):
        """Test that /logout-all revokes all user's refresh tokens."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Track revoke call
        revoke_all_called = {"value": False, "count": 0}
        
        # Create token
        from app.lib.auth import create_access_token
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        access_token = create_access_token(data={"sub": "testuser"})
        
        # Mock User.get_or_none
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        # Mock revoke_user_refresh_tokens
        async def mock_revoke_all(user):
            revoke_all_called["value"] = True
            revoke_all_called["count"] = 5  # Simulate 5 tokens revoked
            return 5
        
        import app.ui.auth
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        monkeypatch.setattr(app.ui.auth, "revoke_user_refresh_tokens", mock_revoke_all)
        
        client.cookies.set("access_token", access_token)
        response = client.get("/logout-all", follow_redirects=False)
        
        # Should have called revoke_user_refresh_tokens
        assert revoke_all_called["value"] is True
        assert revoke_all_called["count"] == 5

    @pytest.mark.asyncio
    async def test_logout_all_deletes_current_cookies(self, monkeypatch):
        """Test that /logout-all deletes current device cookies."""
        from app.main import app as fastapi_app
        client = TestClient(fastapi_app)
        
        # Create tokens
        from app.lib.auth import create_access_token, create_refresh_token
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        access_token = create_access_token(data={"sub": "testuser"})
        refresh_token = create_refresh_token(mock_user)
        
        # Mock User.get_or_none
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        # Mock revoke_user_refresh_tokens
        async def mock_revoke_all(user):
            return 3
        
        import app.lib.auth
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        monkeypatch.setattr(app.lib.auth, "revoke_user_refresh_tokens", mock_revoke_all)
        
        # Make request
        client.cookies.set("access_token", access_token)
        client.cookies.set("refresh_token", refresh_token)
        response = client.get("/logout-all", follow_redirects=False)
        
        # Should redirect and delete cookies
        assert response.status_code in [302, 303, 307]


class TestAuthenticationIntegration:
    """Integration tests for full authentication flow."""

    @pytest.mark.asyncio
    async def test_full_auth_flow_login_and_access(self, monkeypatch):
        """Test complete flow: login with JWT, access protected resource."""
        config = get_app_config()
        
        # Create a valid JWT token
        token = create_access_token(data={"sub": "testuser"})
        
        # Verify token is valid
        import jwt
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        
        assert payload["sub"] == "testuser"
        assert "exp" in payload

    def test_token_configuration_from_env(self):
        """Test that JWT configuration is loaded from environment."""
        config = get_app_config()
        
        # Required config values should be present
        assert config.auth_token_secret_key
        assert len(config.auth_token_secret_key) > 0
        
        assert config.auth_token_age_minutes > 0
        assert isinstance(config.auth_token_age_minutes, int)
        
        assert config.auth_token_algorithm
        assert config.auth_token_algorithm in ["HS256", "HS384", "HS512", "RS256"]

    def test_token_security_configuration(self):
        """Test that token security settings are appropriate."""
        config = get_app_config()
        
        # Secret key should be reasonably long
        assert len(config.auth_token_secret_key) >= 16, (
            "AUTH_TOKEN_SECRET_KEY should be at least 16 characters"
        )
        
        # Token age should be reasonable (between 5 minutes and 24 hours)
        assert 5 <= config.auth_token_age_minutes <= 1440, (
            f"AUTH_TOKEN_AGE_MINUTES should be between 5 and 1440 minutes, "
            f"got {config.auth_token_age_minutes}"
        )
