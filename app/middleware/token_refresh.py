import jwt
from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request

from app.lib.config import get_app_config
from app.lib.auth import (
    get_current_user_from_token,
    get_refresh_token_payload,
    validate_refresh_token,
    set_token_cookies
)

from app.models.users import User


config = get_app_config()


class TokenRefreshMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically refresh access tokens before they expire.
    
    Checks if access token has less than 5 minutes remaining and refreshes
    it transparently using the refresh token if available.
    """
    
    async def dispatch(self, request: Request, call_next):
        # Get access token from cookie
        access_token = request.cookies.get("access_token")
        
        if access_token:
            try:
                # Decode to check expiration (don't validate signature if expired)
                payload = jwt.decode(
                    access_token,
                    config.auth_token_secret_key,
                    algorithms=[config.auth_token_algorithm],
                    options={"verify_exp": False}
                )
                
                exp_timestamp = payload.get("exp")
                if exp_timestamp:
                    expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)
                    time_remaining = (expires_at - datetime.now(timezone.utc)).total_seconds()
                    
                    # If < 5 minutes (300 seconds) remaining, attempt refresh
                    if time_remaining < 300:
                        # Get user from access token
                        user = await get_current_user_from_token(access_token)
                        
                        if user is not None and isinstance(user, User):
                            # Get refresh token from request
                            refresh_token_payload = get_refresh_token_payload(request)
                            
                            if refresh_token_payload:
                                # Validate refresh token against database
                                refresh_token = await validate_refresh_token(
                                    refresh_token_payload,
                                    user.id
                                )
                                
                                if refresh_token:
                                    # Process request first
                                    response = await call_next(request)
                                    
                                    # Then set new tokens on response
                                    await set_token_cookies(response, user, refresh_token)
                                    return response
            
            except (jwt.InvalidTokenError, ValueError, TypeError):
                pass  # Let request proceed normally
        
        # No refresh needed or not authenticated
        return await call_next(request)
