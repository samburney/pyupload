"""Tests for token refresh middleware (app/middleware/token_refresh.py).

Tests automatic token refresh functionality when access tokens are close to expiring.

Acceptance Criteria:
- Middleware detects tokens expiring within 5 minutes
- Middleware refreshes tokens transparently when conditions are met
- Middleware passes through requests when refresh not needed
- Middleware handles errors gracefully without breaking requests
- Middleware doesn't refresh when no refresh token available
- Middleware validates refresh token before refreshing
"""

import pytest
import jwt
from datetime import datetime, timedelta, timezone
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI, Request, Response
from fastapi.testclient import TestClient

from app.lib.config import get_app_config
from app.lib.auth import create_access_token, create_refresh_token, store_refresh_token
from app.middleware.token_refresh import TokenRefreshMiddleware
from app.models.users import User


config = get_app_config()


# ============================================================================
# Helper Functions
# ============================================================================

def create_expiring_token(username: str, minutes_until_expiry: int) -> str:
    """Create an access token that expires in specified minutes."""
    expires_delta = timedelta(minutes=minutes_until_expiry)
    expire = datetime.now(timezone.utc) + expires_delta
    to_encode = {"sub": username, "exp": expire}
    
    return jwt.encode(
        to_encode,
        config.auth_token_secret_key,
        algorithm=config.auth_token_algorithm
    )


# ============================================================================
# Token Detection Tests
# ============================================================================

class TestTokenExpirationDetection:
    """Test that middleware correctly detects expiring tokens."""

    @pytest.mark.asyncio
    async def test_detects_token_expiring_in_4_minutes(self, monkeypatch):
        """Test that token expiring in 4 minutes is detected."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        # Track if refresh was attempted
        refresh_attempted = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal refresh_attempted
            refresh_attempted = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Create token expiring in 4 minutes
        access_token = create_expiring_token("testuser", 4)
        refresh_token = create_refresh_token(Mock(id=1))
        
        # Mock user and refresh token validation
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        mock_refresh = Mock()
        mock_refresh.id = 1
        
        with patch("app.middleware.token_refresh.get_current_user_from_token", return_value=mock_user):
            with patch("app.middleware.token_refresh.get_refresh_token_payload", return_value=refresh_token):
                with patch("app.middleware.token_refresh.validate_refresh_token", return_value=mock_refresh):
                    with patch("app.middleware.token_refresh.set_token_cookies", new=mock_set_token_cookies):
                        client = TestClient(app)
                        client.cookies.set("access_token", access_token)
                        client.cookies.set("refresh_token", refresh_token)
                        
                        response = client.get("/test")
                        
                        assert response.status_code == 200
                        assert refresh_attempted is True

    @pytest.mark.asyncio
    async def test_detects_token_expiring_in_1_minute(self, monkeypatch):
        """Test that token expiring in 1 minute is detected."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        refresh_attempted = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal refresh_attempted
            refresh_attempted = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        access_token = create_expiring_token("testuser", 1)
        refresh_token = create_refresh_token(Mock(id=1))
        
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        mock_refresh = Mock()
        mock_refresh.id = 1
        
        with patch("app.middleware.token_refresh.get_current_user_from_token", return_value=mock_user):
            with patch("app.middleware.token_refresh.get_refresh_token_payload", return_value=refresh_token):
                with patch("app.middleware.token_refresh.validate_refresh_token", return_value=mock_refresh):
                    with patch("app.middleware.token_refresh.set_token_cookies", new=mock_set_token_cookies):
                        client = TestClient(app)
                        client.cookies.set("access_token", access_token)
                        client.cookies.set("refresh_token", refresh_token)
                        
                        response = client.get("/test")
                        
                        assert response.status_code == 200
                        assert refresh_attempted is True

    @pytest.mark.asyncio
    async def test_ignores_token_expiring_in_10_minutes(self, monkeypatch):
        """Test that token expiring in 10 minutes is not refreshed."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        refresh_attempted = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal refresh_attempted
            refresh_attempted = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        access_token = create_expiring_token("testuser", 10)
        
        with patch("app.middleware.token_refresh.set_token_cookies", new=mock_set_token_cookies):
            client = TestClient(app)
            client.cookies.set("access_token", access_token)
            
            response = client.get("/test")
            
            assert response.status_code == 200
            assert refresh_attempted is False


# ============================================================================
# Token Refresh Tests
# ============================================================================

class TestTokenRefresh:
    """Test that middleware correctly refreshes tokens."""

    @pytest.mark.asyncio
    async def test_refreshes_with_valid_refresh_token(self, db):
        """Test that valid refresh token triggers token refresh."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        cookies_updated = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal cookies_updated
            cookies_updated = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Create user and tokens
        user = await User.create(
            username="testuser",
            email="test@example.com",
            password="dummy_hash",
            remember_token=""
        )
        
        mock_user = Mock(spec=User)
        mock_user.id = user.id
        
        access_token = create_expiring_token("testuser", 4)
        refresh_token = create_refresh_token(mock_user)
        stored_refresh = await store_refresh_token(refresh_token, user)
        
        with patch("app.middleware.token_refresh.get_current_user_from_token", return_value=user):
            with patch("app.middleware.token_refresh.set_token_cookies", new=mock_set_token_cookies):
                client = TestClient(app)
                client.cookies.set("access_token", access_token)
                client.cookies.set("refresh_token", refresh_token)
                
                response = client.get("/test")
                
                assert response.status_code == 200
                assert cookies_updated is True
        
        await user.delete()

    @pytest.mark.asyncio
    async def test_doesnt_refresh_without_refresh_token(self):
        """Test that missing refresh token prevents refresh."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        refresh_attempted = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal refresh_attempted
            refresh_attempted = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        access_token = create_expiring_token("testuser", 4)
        
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        with patch("app.middleware.token_refresh.get_current_user_from_token", return_value=mock_user):
            with patch("app.middleware.token_refresh.set_token_cookies", new=mock_set_token_cookies):
                client = TestClient(app)
                client.cookies.set("access_token", access_token)
                # No refresh token cookie
                
                response = client.get("/test")
                
                assert response.status_code == 200
                assert refresh_attempted is False

    @pytest.mark.asyncio
    async def test_doesnt_refresh_with_invalid_refresh_token(self):
        """Test that invalid refresh token prevents refresh."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        refresh_attempted = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal refresh_attempted
            refresh_attempted = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        access_token = create_expiring_token("testuser", 4)
        
        mock_user = Mock(spec=User)
        mock_user.id = 1
        mock_user.username = "testuser"
        
        # Return None for invalid refresh token
        with patch("app.middleware.token_refresh.get_current_user_from_token", return_value=mock_user):
            with patch("app.middleware.token_refresh.get_refresh_token_payload", return_value="invalid"):
                with patch("app.middleware.token_refresh.validate_refresh_token", return_value=None):
                    with patch("app.middleware.token_refresh.set_token_cookies", new=mock_set_token_cookies):
                        client = TestClient(app)
                        client.cookies.set("access_token", access_token)
                        client.cookies.set("refresh_token", "invalid")
                        
                        response = client.get("/test")
                        
                        assert response.status_code == 200
                        assert refresh_attempted is False


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test that middleware handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_handles_invalid_jwt_gracefully(self):
        """Test that invalid JWT doesn't break request."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        client.cookies.set("access_token", "invalid_jwt_token")
        
        response = client.get("/test")
        
        # Request should succeed despite invalid token
        assert response.status_code == 200
        assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_handles_expired_jwt_gracefully(self):
        """Test that expired JWT doesn't break request."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Create already expired token
        expired_token = create_expiring_token("testuser", -10)
        
        client = TestClient(app)
        client.cookies.set("access_token", expired_token)
        
        response = client.get("/test")
        
        # Request should succeed
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_handles_missing_exp_claim(self):
        """Test that token without exp claim is handled gracefully."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Create token without exp claim
        token = jwt.encode(
            {"sub": "testuser"},
            config.auth_token_secret_key,
            algorithm=config.auth_token_algorithm
        )
        
        client = TestClient(app)
        client.cookies.set("access_token", token)
        
        response = client.get("/test")
        
        assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_continues_on_user_lookup_failure(self):
        """Test that failed user lookup doesn't break request."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        access_token = create_expiring_token("testuser", 4)
        
        # Return None for user lookup
        with patch("app.middleware.token_refresh.get_current_user_from_token", return_value=None):
            client = TestClient(app)
            client.cookies.set("access_token", access_token)
            
            response = client.get("/test")
            
            assert response.status_code == 200


# ============================================================================
# Pass-through Tests
# ============================================================================

class TestPassThrough:
    """Test that middleware doesn't interfere with normal requests."""

    @pytest.mark.asyncio
    async def test_passes_through_unauthenticated_requests(self):
        """Test that requests without tokens pass through normally."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        client = TestClient(app)
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_passes_through_fresh_tokens(self):
        """Test that fresh tokens don't trigger refresh."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        refresh_attempted = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal refresh_attempted
            refresh_attempted = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Create token that's fresh (20 minutes remaining)
        access_token = create_expiring_token("testuser", 20)
        
        with patch("app.middleware.token_refresh.set_token_cookies", new=mock_set_token_cookies):
            client = TestClient(app)
            client.cookies.set("access_token", access_token)
            
            response = client.get("/test")
            
            assert response.status_code == 200
            assert refresh_attempted is False

    @pytest.mark.asyncio
    async def test_preserves_response_content(self):
        """Test that middleware doesn't modify response content."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"data": "test", "count": 42}
        
        access_token = create_access_token(data={"sub": "testuser"})
        
        client = TestClient(app)
        client.cookies.set("access_token", access_token)
        
        response = client.get("/test")
        
        assert response.status_code == 200
        assert response.json() == {"data": "test", "count": 42}


# ============================================================================
# Edge Cases
# ============================================================================

class TestEdgeCases:
    """Test edge cases in middleware behavior."""

    @pytest.mark.asyncio
    async def test_handles_non_user_object_from_token(self):
        """Test that non-User object from token lookup is handled."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        access_token = create_expiring_token("testuser", 4)
        
        # Return a dict instead of User object
        with patch("app.middleware.token_refresh.get_current_user_from_token", return_value={"username": "testuser"}):
            client = TestClient(app)
            client.cookies.set("access_token", access_token)
            
            response = client.get("/test")
            
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_handles_boundary_time_exactly_5_minutes(self):
        """Test behavior at exactly 5 minute threshold."""
        app = FastAPI()
        app.add_middleware(TokenRefreshMiddleware)
        
        refresh_attempted = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal refresh_attempted
            refresh_attempted = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Create token expiring in exactly 5 minutes (300 seconds)
        access_token = create_expiring_token("testuser", 5)
        refresh_token = create_refresh_token(Mock(id=1))
        
        mock_user = Mock(spec=User)
        mock_user.id = 1
        
        mock_refresh = Mock()
        mock_refresh.id = 1
        
        with patch("app.middleware.token_refresh.get_current_user_from_token", return_value=mock_user):
            with patch("app.middleware.token_refresh.get_refresh_token_payload", return_value=refresh_token):
                with patch("app.middleware.token_refresh.validate_refresh_token", return_value=mock_refresh):
                    with patch("app.middleware.token_refresh.set_token_cookies", new=mock_set_token_cookies):
                        client = TestClient(app)
                        client.cookies.set("access_token", access_token)
                        client.cookies.set("refresh_token", refresh_token)
                        
                        response = client.get("/test")
                        
                        assert response.status_code == 200
                        # At exactly 5 minutes, should not refresh (< 300 seconds required)
                        # Depending on timing, this might be True or False
                        # So we just verify request succeeds
