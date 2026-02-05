import jwt

from typing import Self
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

from app.lib.config import get_app_config, logger
from app.lib.auth import (
    get_current_user_from_token,
    get_refresh_token_payload,
    validate_refresh_token,
    set_token_cookies,
    get_current_user_from_request,
)

from app.models.users import User


config = get_app_config()


class TokenRefreshMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically refresh access tokens before they expire.
    
    Checks if access token has less than 5 minutes remaining and refreshes
    it transparently using the refresh token if available.
    """
    
    async def dispatch(self, request: Request, call_next): # type: ignore[override]
        """Handle access token refresh transparently on each request."""

        # Get access token from cookie
        access_token_payload = request.cookies.get("access_token")
        refresh_token_payload = get_refresh_token_payload(request)

        # If access token is present, check if it needs refreshing
        if access_token_payload:
            try:
                # Decode to check expiration (don't validate signature if expired)
                access_token_data = jwt.decode(
                    access_token_payload,
                    config.auth_token_secret_key,
                    algorithms=[config.auth_token_algorithm],
                    options={"verify_exp": False}
                )
                
                exp_timestamp = access_token_data.get("exp")
                if exp_timestamp:
                    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                    time_remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()

                    # If < 5 minutes (300 seconds) remaining, attempt refresh
                    if time_remaining < 300:
                        # Do access token refresh
                        try:
                            return await self.do_access_token_refresh(request, call_next)
                        except Exception as e:
                            pass  # Let request proceed normally

            except (jwt.InvalidTokenError, ValueError, TypeError):
                pass  # Let request proceed normally
        
        # If refresh token is present, refresh access token
        elif refresh_token_payload:
            try:
                return await self.do_access_token_refresh(request, call_next)
            except Exception as e:
                pass  # Let request proceed normally

        # No refresh needed or not authenticated
        return await call_next(request)

    async def do_access_token_refresh(self: Self, request: Request, call_next):
        """Refresh access token using refresh token."""

        # Get refresh token from request
        refresh_token_payload = get_refresh_token_payload(request)
        if refresh_token_payload is None:
            raise Exception("Refresh token not found")

        # Get user from refresh token
        user = await get_current_user_from_token(refresh_token_payload)
        if user is None or not isinstance(user, User):
            raise Exception("Invalid refresh token")

        # Do access token refresh
        if refresh_token_payload:
            # Validate refresh token against database
            validated_refresh_token = await validate_refresh_token(
                refresh_token_payload,
                user.id
            )
            if validated_refresh_token:
                # Inject user into request state so downstream auth checks work
                # even though the new access token cookie is only on the response
                request.state.user = user
                
                # Process request with authenticated user context
                response = await call_next(request)
                
                # Then set new tokens on response
                await set_token_cookies(response, user, validated_refresh_token)

                logger.info(f"Access token refreshed for user: {user.username}")

                return response

            else:
                raise Exception("Invalid refresh token")
