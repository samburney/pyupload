from datetime import datetime, timezone
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi import Request
from tortoise.exceptions import ConfigurationError, OperationalError

from app.lib.config import get_app_config
from app.lib.security import get_request_ip
from app.lib.auth import (
    get_current_user_from_request,
    get_unregistered_user_by_fingerprint,
    set_token_cookies,
)


config = get_app_config()


class FingerprintAutoLoginMiddleware(BaseHTTPMiddleware):
    """Middleware to automatically log in unregistered users based on
    client fingerprint.
    
    If a request comes in without an authenticated user but with a matching
    fingerprint hash in the database, the corresponding unregistered user
    is automatically logged in for the duration of the session.
    """
    
    async def dispatch(self, request: Request, call_next):
        is_authenticated = False
        autologin_user = None

        try:
            # Check if user is already authenticated
            if await get_current_user_from_request(request) is not None:
                is_authenticated = True

            # If not authenticated, check for existing unregistered user by fingerprint
            if not is_authenticated:
                unregistered_user = await get_unregistered_user_by_fingerprint(request)
                if unregistered_user:
                    # Update database last active timestamp or other info if needed
                    unregistered_user.last_login_ip = str(get_request_ip(request))
                    unregistered_user.last_seen_at = datetime.now(timezone.utc)
                    await unregistered_user.save()

                    # Mark user for login
                    autologin_user = unregistered_user
                else:
                    # Do nothing, user should remain anonymous unless they attempt
                    # to use a feature that requires a user account.
                    pass
        except (ConfigurationError, OperationalError):
            # Database not initialized or not available - skip auto-login
            pass

        # Get the response first
        response = await call_next(request)
        
        # Now set cookies on the response if needed
        if autologin_user is not None:
            await set_token_cookies(response, autologin_user)
        
        return response
