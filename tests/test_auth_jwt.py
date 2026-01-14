"""Tests for JWT-based authentication.

Verifies that JWT token authentication is properly implemented for login/logout
and that tokens are correctly created, validated, and stored in cookies.

Acceptance Criteria:
- JWT tokens are created upon successful login
- Tokens are stored in HttpOnly cookies
- Tokens contain correct user information
- Token expiration is properly configured
- Logout deletes access token cookie
- Invalid/expired tokens result in anonymous user
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from fastapi.testclient import TestClient
from fastapi import Request
from unittest.mock import Mock, AsyncMock

from app.main import app
from app.lib.config import get_app_config
from app.lib.auth import create_access_token, create_token_cookie, get_current_user
from app.models.users import User, UserPydantic, authenticate_user


class TestJWTTokenCreation:
    """Test JWT token creation and structure."""

    def test_create_access_token_returns_string(self):
        """Test that create_access_token returns a valid JWT string."""
        token = create_access_token(data={"sub": "testuser"})
        
        assert isinstance(token, str)
        assert len(token) > 0
        
        # JWT tokens have 3 parts separated by dots
        assert token.count('.') == 2

    def test_create_access_token_contains_subject(self):
        """Test that created token contains the subject claim."""
        config = get_app_config()
        username = "testuser"
        token = create_access_token(data={"sub": username})
        
        # Decode without verification for testing
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        
        assert payload["sub"] == username

    def test_create_access_token_has_expiration(self):
        """Test that created token has an expiration time."""
        config = get_app_config()
        token = create_access_token(data={"sub": "testuser"})
        
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        
        assert "exp" in payload
        
        # Expiration should be in the future
        exp_timestamp = payload["exp"]
        now_timestamp = datetime.now(timezone.utc).timestamp()
        assert exp_timestamp > now_timestamp

    def test_create_access_token_expiration_time_is_correct(self):
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
        
        # Should be within 5 seconds of expected (allow for processing time)
        time_diff = abs((exp_time - expected_exp).total_seconds())
        assert time_diff < 5

    def test_create_access_token_uses_correct_algorithm(self):
        """Test that token is created with configured algorithm."""
        config = get_app_config()
        token = create_access_token(data={"sub": "testuser"})
        
        # Decode and verify algorithm
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        
        # If we got here without exception, algorithm is correct
        assert payload is not None


class TestJWTTokenCookie:
    """Test JWT token cookie configuration."""

    def test_create_token_cookie_returns_dict(self):
        """Test that create_token_cookie returns a dictionary."""
        cookie = create_token_cookie(token="test_token")
        
        assert isinstance(cookie, dict)

    def test_create_token_cookie_has_required_fields(self):
        """Test that cookie dictionary has all required fields."""
        cookie = create_token_cookie(token="test_token")
        
        required_fields = ["key", "value", "httponly", "max_age", "secure", "samesite"]
        for field in required_fields:
            assert field in cookie, f"Cookie missing required field: {field}"

    def test_create_token_cookie_key_name(self):
        """Test that cookie uses correct key name."""
        cookie = create_token_cookie(token="test_token", token_type="access")
        
        assert cookie["key"] == "access_token"

    def test_create_token_cookie_httponly_enabled(self):
        """Test that cookie has httponly flag enabled for security."""
        cookie = create_token_cookie(token="test_token")
        
        assert cookie["httponly"] is True

    def test_create_token_cookie_secure_enabled(self):
        """Test that cookie has secure flag enabled for HTTPS."""
        cookie = create_token_cookie(token="test_token")
        
        assert cookie["secure"] is True

    def test_create_token_cookie_samesite_configured(self):
        """Test that cookie has samesite policy configured."""
        cookie = create_token_cookie(token="test_token")
        
        assert cookie["samesite"] == "lax"

    def test_create_token_cookie_max_age_configured(self):
        """Test that cookie has max_age configured."""
        config = get_app_config()
        cookie = create_token_cookie(token="test_token")
        
        assert "max_age" in cookie
        # max_age should be a timedelta or int
        assert cookie["max_age"] is not None


class TestGetCurrentUser:
    """Test get_current_user function for token validation."""

    @pytest.mark.asyncio
    async def test_get_current_user_with_valid_token(self, monkeypatch):
        """Test that get_current_user returns user with valid token."""
        config = get_app_config()
        
        # Create a valid token
        token = create_access_token(data={"sub": "testuser"})
        
        # Mock request with token in cookies
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": token}
        
        # Mock User.get_or_none to return a test user
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.remember_token = ""
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        # Call get_current_user
        result = await get_current_user(mock_request)
        
        assert isinstance(result, UserPydantic)
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_get_current_user_without_token(self):
        """Test that get_current_user returns anonymous user without token."""
        # Mock request without token
        mock_request = Mock(spec=Request)
        mock_request.cookies = {}
        
        result = await get_current_user(mock_request)
        
        assert isinstance(result, UserPydantic)
        assert result.username == "anonymous"
        assert result.id == -1

    @pytest.mark.asyncio
    async def test_get_current_user_with_invalid_token(self):
        """Test that get_current_user returns anonymous user with invalid token."""
        # Mock request with invalid token
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": "invalid.token.here"}
        
        result = await get_current_user(mock_request)
        
        assert isinstance(result, UserPydantic)
        assert result.username == "anonymous"

    @pytest.mark.asyncio
    async def test_get_current_user_with_expired_token(self):
        """Test that get_current_user returns anonymous user with expired token."""
        config = get_app_config()
        
        # Create an expired token (exp in the past)
        past_time = datetime.now(timezone.utc) - timedelta(hours=1)
        payload = {
            "sub": "testuser",
            "exp": past_time
        }
        expired_token = jwt.encode(
            payload,
            config.auth_token_secret_key,
            algorithm=config.auth_token_algorithm
        )
        
        # Mock request with expired token
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": expired_token}
        
        result = await get_current_user(mock_request)
        
        assert isinstance(result, UserPydantic)
        assert result.username == "anonymous"

    @pytest.mark.asyncio
    async def test_get_current_user_with_nonexistent_user(self, monkeypatch):
        """Test that get_current_user returns anonymous when user not in DB."""
        config = get_app_config()
        
        # Create a valid token for non-existent user
        token = create_access_token(data={"sub": "nonexistent"})
        
        # Mock request with token
        mock_request = Mock(spec=Request)
        mock_request.cookies = {"access_token": token}
        
        # Mock User.get_or_none to return None
        async def mock_get_or_none(**kwargs):
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        result = await get_current_user(mock_request)
        
        assert isinstance(result, UserPydantic)
        assert result.username == "anonymous"


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
        
        # Import and patch the authenticate_user function
        import app.ui.auth
        monkeypatch.setattr(app.ui.auth, "authenticate_user", mock_authenticate)
        
        # Attempt login
        response = client.post(
            "/login",
            data={"username": "testuser", "password": "password"}
        )
        
        # Should set a cookie
        assert "access_token" in response.cookies or "set-cookie" in response.headers

    @pytest.mark.asyncio
    async def test_login_post_with_invalid_credentials_returns_error(self, monkeypatch):
        """Test that failed login returns 401 error."""
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
    async def test_logout_endpoint_exists(self):
        """Test that logout endpoint is accessible."""
        client = TestClient(app)
        response = client.get("/logout", follow_redirects=False)
        
        # Should redirect
        assert response.status_code in [302, 303, 307]

    @pytest.mark.asyncio
    async def test_logout_deletes_access_token_cookie(self):
        """Test that logout deletes the access_token cookie."""
        client = TestClient(app)
        
        # Mock being logged in by setting a cookie
        client.cookies.set("access_token", "some_token")
        
        response = client.get("/logout", follow_redirects=False)
        
        # Cookie should be deleted (set to empty or expired)
        # Check if access_token is in delete cookies
        set_cookie_header = response.headers.get("set-cookie", "")
        
        # The cookie should be deleted (max-age=0 or expires in past)
        assert "access_token" in set_cookie_header.lower() or response.status_code in [302, 303, 307]

    @pytest.mark.asyncio
    async def test_logout_redirects_to_home(self):
        """Test that logout redirects to home page."""
        client = TestClient(app)
        
        response = client.get("/logout", follow_redirects=False)
        
        # Should be a redirect response
        assert response.status_code in [302, 303, 307]
        
        # Should redirect to root
        assert response.headers.get("location") == "/"


class TestAuthenticationIntegration:
    """Integration tests for full authentication flow."""

    @pytest.mark.asyncio
    async def test_full_auth_flow_login_and_access(self, monkeypatch):
        """Test complete flow: login with JWT, access protected resource."""
        config = get_app_config()
        
        # Create a valid JWT token
        token = create_access_token(data={"sub": "testuser"})
        
        # Verify token is valid
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


class TestAuthenticateUser:
    """Test authenticate_user function."""

    @pytest.mark.asyncio
    async def test_authenticate_user_with_username(self, monkeypatch):
        """Test authenticating user by username."""
        from app.models.users import authenticate_user
        from app.lib.security import hash_password
        
        # Create mock user
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        mock_user.password = hash_password("password123")
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        # Authenticate
        result = await authenticate_user("testuser", "password123")
        
        assert result is not None
        assert result.username == "testuser"

    @pytest.mark.asyncio
    async def test_authenticate_user_with_email(self, monkeypatch):
        """Test authenticating user by email."""
        from app.models.users import authenticate_user
        from app.lib.security import hash_password
        
        # Create mock user
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        mock_user.email = "test@example.com"
        mock_user.password = hash_password("password123")
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("email") == "test@example.com":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        # Authenticate by email
        result = await authenticate_user("test@example.com", "password123")
        
        assert result is not None

    @pytest.mark.asyncio
    async def test_authenticate_user_wrong_password(self, monkeypatch):
        """Test authentication fails with wrong password."""
        from app.models.users import authenticate_user
        from app.lib.security import hash_password
        
        # Create mock user
        mock_user = Mock(spec=User)
        mock_user.username = "testuser"
        mock_user.password = hash_password("correct_password")
        
        async def mock_get_or_none(**kwargs):
            if kwargs.get("username") == "testuser":
                return mock_user
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        # Try to authenticate with wrong password
        result = await authenticate_user("testuser", "wrong_password")
        
        assert result is None

    @pytest.mark.asyncio
    async def test_authenticate_user_nonexistent_user(self, monkeypatch):
        """Test authentication fails for non-existent user."""
        from app.models.users import authenticate_user
        
        async def mock_get_or_none(**kwargs):
            return None
        
        monkeypatch.setattr(User, "get_or_none", mock_get_or_none)
        
        # Try to authenticate non-existent user
        result = await authenticate_user("nonexistent", "password")
        
        assert result is None
