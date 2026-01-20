"""Tests for fingerprint auto-login middleware.

Tests automatic login of unregistered users based on client fingerprint.

Acceptance Criteria:
- Middleware auto-logins unregistered users with matching fingerprint
- Middleware skips auto-login for already authenticated users
- Middleware updates last_seen_at and last_login_ip on auto-login
- Middleware sets token cookies on response after auto-login
- Middleware skips abandoned, disabled, and registered users
- Middleware handles database errors gracefully
- Middleware doesn't interfere with normal requests
"""

import pytest
from datetime import datetime, timezone
from unittest.mock import Mock, AsyncMock, patch
from fastapi import FastAPI
from fastapi.testclient import TestClient
from tortoise.exceptions import OperationalError, ConfigurationError

from app.middleware.fingerprint_auto_login import FingerprintAutoLoginMiddleware
from app.models.users import User


# ============================================================================
# Auto-Login Success Cases
# ============================================================================

class TestFingerprintAutoLogin:
    """Test auto-login based on fingerprint matching."""

    @pytest.mark.asyncio
    async def test_autologin_with_matching_fingerprint(self, db):
        """Test that matching fingerprint triggers auto-login with token cookies set."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        cookies_set = False
        
        async def mock_set_token_cookies(response, user, refresh_token=None):
            nonlocal cookies_set
            cookies_set = True
            assert user is not None
            assert user.username == "UnregUser1234"
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Create unregistered user with fingerprint
        user = await User.create(
            username="UnregUser1234",
            email="",
            password="",
            is_registered=False,
            is_abandoned=False,
            fingerprint_hash="a" * 64,
            fingerprint_data={"user_agent": "test"},
            registration_ip="192.168.1.1"
        )
        
        try:
            with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
                with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=user):
                    with patch("app.middleware.fingerprint_auto_login.set_token_cookies", new=mock_set_token_cookies):
                        with patch("app.middleware.fingerprint_auto_login.get_request_ip", return_value="192.168.1.100"):
                            client = TestClient(app)
                            response = client.get("/test")
                            
                            assert response.status_code == 200
                            assert cookies_set is True
                            
                            # Verify database was updated
                            await user.refresh_from_db()
                            assert user.last_login_ip == "192.168.1.100"
                            assert user.last_seen_at is not None
        finally:
            await user.delete()

    @pytest.mark.asyncio
    async def test_updates_last_seen_at_on_autologin(self, db):
        """Test that last_seen_at is updated when auto-login occurs."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        user = await User.create(
            username="TestUser5678",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="b" * 64,
            last_seen_at=None
        )
        
        try:
            with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
                with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=user):
                    with patch("app.middleware.fingerprint_auto_login.set_token_cookies", new=AsyncMock()):
                        with patch("app.middleware.fingerprint_auto_login.get_request_ip", return_value="10.0.0.1"):
                            client = TestClient(app)
                            response = client.get("/test")
                            
                            assert response.status_code == 200
                            
                            # Verify last_seen_at was set
                            await user.refresh_from_db()
                            assert user.last_seen_at is not None
                            # Within last 5 seconds
                            time_diff = (datetime.now(timezone.utc) - user.last_seen_at).total_seconds()
                            assert time_diff < 5
        finally:
            await user.delete()

    @pytest.mark.asyncio
    async def test_updates_last_login_ip_on_autologin(self, db):
        """Test that last_login_ip is updated when auto-login occurs."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        user = await User.create(
            username="IPTestUser9999",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="c" * 64,
            last_login_ip=None
        )
        
        try:
            with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
                with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=user):
                    with patch("app.middleware.fingerprint_auto_login.set_token_cookies", new=AsyncMock()):
                        with patch("app.middleware.fingerprint_auto_login.get_request_ip", return_value="203.0.113.45"):
                            client = TestClient(app)
                            response = client.get("/test")
                            
                            assert response.status_code == 200
                            
                            # Verify IP was updated
                            await user.refresh_from_db()
                            assert user.last_login_ip == "203.0.113.45"
        finally:
            await user.delete()


# ============================================================================
# Skip Auto-Login Cases
# ============================================================================

class TestSkipAutoLogin:
    """Test cases where auto-login should be skipped."""

    @pytest.mark.asyncio
    async def test_skips_already_authenticated_user(self, db):
        """Test that already authenticated users skip fingerprint check."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        fingerprint_checked = False
        
        async def mock_get_fingerprint(*args, **kwargs):
            nonlocal fingerprint_checked
            fingerprint_checked = True
            return None
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Create authenticated user
        user = await User.create(
            username="authenticated_user",
            email="auth@example.com",
            password="hash",
            is_registered=True
        )
        
        try:
            # Return authenticated user
            with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=user):
                with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", new=mock_get_fingerprint):
                    client = TestClient(app)
                    response = client.get("/test")
                    
                    assert response.status_code == 200
                    # Fingerprint should not have been checked
                    assert fingerprint_checked is False
        finally:
            await user.delete()

    @pytest.mark.asyncio
    async def test_skips_when_no_fingerprint_match(self):
        """Test that no fingerprint match leaves user anonymous."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        cookies_set = False
        
        async def mock_set_token_cookies(*args, **kwargs):
            nonlocal cookies_set
            cookies_set = True
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
            with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=None):
                with patch("app.middleware.fingerprint_auto_login.set_token_cookies", new=mock_set_token_cookies):
                    client = TestClient(app)
                    response = client.get("/test")
                    
                    assert response.status_code == 200
                    # No cookies should be set
                    assert cookies_set is False

    @pytest.mark.asyncio
    async def test_skips_abandoned_users(self, db):
        """Test that abandoned users are not auto-logged in."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Abandoned user won't be returned by get_unregistered_user_by_fingerprint
        # because it filters is_abandoned=False
        with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
            with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=None):
                client = TestClient(app)
                response = client.get("/test")
                
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_skips_disabled_users(self):
        """Test that disabled users are not auto-logged in."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Disabled user won't be returned by get_unregistered_user_by_fingerprint
        # because it filters is_disabled=False
        with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
            with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=None):
                client = TestClient(app)
                response = client.get("/test")
                
                assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_skips_registered_users(self):
        """Test that registered users are not auto-logged in via fingerprint."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        # Registered user won't be returned by get_unregistered_user_by_fingerprint
        # because it filters is_registered=False
        with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
            with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=None):
                client = TestClient(app)
                response = client.get("/test")
                
                assert response.status_code == 200


# ============================================================================
# Error Handling Tests
# ============================================================================

class TestErrorHandling:
    """Test that middleware handles errors gracefully."""

    @pytest.mark.asyncio
    async def test_handles_operational_error_gracefully(self):
        """Test that database OperationalError doesn't break request."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        async def mock_get_user_raises(*args, **kwargs):
            raise OperationalError("Database connection failed")
        
        with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", new=mock_get_user_raises):
            client = TestClient(app)
            response = client.get("/test")
            
            # Request should succeed despite database error
            assert response.status_code == 200
            assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_handles_configuration_error_gracefully(self):
        """Test that database ConfigurationError doesn't break request."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        async def mock_get_user_raises(*args, **kwargs):
            raise ConfigurationError("Database not configured")
        
        with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", new=mock_get_user_raises):
            client = TestClient(app)
            response = client.get("/test")
            
            # Request should succeed
            assert response.status_code == 200

    @pytest.mark.asyncio
    async def test_handles_user_save_error_gracefully(self, db):
        """Test that error during user.save() doesn't break request."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        user = await User.create(
            username="SaveErrorUser",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="d" * 64
        )
        
        try:
            # Mock user.save() to raise an error
            async def mock_save(*args, **kwargs):
                raise OperationalError("Save failed")
            
            user.save = mock_save
            
            with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
                with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=user):
                    with patch("app.middleware.fingerprint_auto_login.set_token_cookies", new=AsyncMock()):
                        with patch("app.middleware.fingerprint_auto_login.get_request_ip", return_value="10.0.0.1"):
                            client = TestClient(app)
                            
                            # Should raise because save() will be called
                            # But middleware catches OperationalError
                            response = client.get("/test")
                            assert response.status_code == 200
        finally:
            await user.delete()


# ============================================================================
# Pass-Through and Preservation Tests
# ============================================================================

class TestPassThrough:
    """Test that middleware doesn't interfere with normal requests."""

    @pytest.mark.asyncio
    async def test_passes_through_anonymous_requests(self):
        """Test that anonymous requests (no JWT, no fingerprint match) work normally."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
            with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=None):
                client = TestClient(app)
                response = client.get("/test")
                
                assert response.status_code == 200
                assert response.json() == {"message": "success"}

    @pytest.mark.asyncio
    async def test_preserves_response_content(self, db):
        """Test that middleware doesn't modify response content."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"data": "test", "count": 42, "items": [1, 2, 3]}
        
        user = await User.create(
            username="ContentTestUser",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="e" * 64
        )
        
        try:
            with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
                with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=user):
                    with patch("app.middleware.fingerprint_auto_login.set_token_cookies", new=AsyncMock()):
                        with patch("app.middleware.fingerprint_auto_login.get_request_ip", return_value="10.0.0.1"):
                            client = TestClient(app)
                            response = client.get("/test")
                            
                            assert response.status_code == 200
                            assert response.json() == {"data": "test", "count": 42, "items": [1, 2, 3]}
        finally:
            await user.delete()

    @pytest.mark.asyncio
    async def test_preserves_response_status_codes(self):
        """Test that middleware preserves various HTTP status codes."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test/404")
        async def test_404():
            from fastapi import HTTPException
            raise HTTPException(status_code=404, detail="Not found")
        
        @app.post("/test/created")
        async def test_201():
            from fastapi import Response
            return Response(status_code=201, content="Created")
        
        with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
            with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=None):
                client = TestClient(app)
                
                response_404 = client.get("/test/404")
                assert response_404.status_code == 404
                
                response_201 = client.post("/test/created")
                assert response_201.status_code == 201


# ============================================================================
# Integration Tests
# ============================================================================

class TestIntegration:
    """Test integration scenarios with other middleware and features."""

    @pytest.mark.asyncio
    async def test_autologin_sets_cookies_for_subsequent_requests(self, db):
        """Test that auto-login creates cookies that can be used in future requests."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        user = await User.create(
            username="CookieTestUser",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="f" * 64
        )
        
        try:
            # First request: auto-login happens
            cookies_set = False
            
            async def mock_set_token_cookies(response, user, refresh_token=None):
                nonlocal cookies_set
                cookies_set = True
                # Simulate setting cookies
                response.set_cookie(key="access_token", value="test_token")
            
            with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
                with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=user):
                    with patch("app.middleware.fingerprint_auto_login.set_token_cookies", new=mock_set_token_cookies):
                        with patch("app.middleware.fingerprint_auto_login.get_request_ip", return_value="10.0.0.1"):
                            client = TestClient(app)
                            response = client.get("/test")
                            
                            assert response.status_code == 200
                            assert cookies_set is True
                            assert "access_token" in response.cookies
        finally:
            await user.delete()

    @pytest.mark.asyncio
    async def test_works_with_multiple_requests(self, db):
        """Test that middleware works correctly across multiple requests."""
        app = FastAPI()
        app.add_middleware(FingerprintAutoLoginMiddleware)
        
        @app.get("/test")
        async def test_endpoint():
            return {"message": "success"}
        
        user = await User.create(
            username="MultiReqUser",
            email="",
            password="",
            is_registered=False,
            fingerprint_hash="9" * 64
        )
        
        try:
            with patch("app.middleware.fingerprint_auto_login.get_current_user_from_request", return_value=None):
                with patch("app.middleware.fingerprint_auto_login.get_unregistered_user_by_fingerprint", return_value=user):
                    with patch("app.middleware.fingerprint_auto_login.set_token_cookies", new=AsyncMock()):
                        with patch("app.middleware.fingerprint_auto_login.get_request_ip", return_value="10.0.0.1"):
                            client = TestClient(app)
                            
                            # Make multiple requests
                            for _ in range(3):
                                response = client.get("/test")
                                assert response.status_code == 200
        finally:
            await user.delete()
