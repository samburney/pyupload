import jwt

from datetime import datetime, timedelta, timezone
from pydantic import BaseModel
from fastapi import Request
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm

from app.lib.config import get_app_config

from app.models.users import User, UserPydantic


config = get_app_config()


async def get_current_user(request: Request) -> None | UserPydantic:
    """Dependency to get the current authenticated user from the session."""
    
    # Validate access token from cookie
    access_token = request.cookies.get("access_token")

    if access_token:
        try:
            payload = jwt.decode(
                access_token,
                config.auth_token_secret_key,
                algorithms=[config.auth_token_algorithm]
            )
            username = payload.get("sub")

            # Get user from DB
            if type(username) is str:
                user = await User.get_or_none(username=username)
                if user:
                    return await UserPydantic.from_tortoise_orm(user)

        # Return anonymous user on token errors
        except jwt.ExpiredSignatureError:
            # Token has expired
            return UserPydantic.anonymous_user()
        except jwt.DecodeError:
            # Token is invalid or malformed
            return UserPydantic.anonymous_user()
        except jwt.InvalidTokenError:
            # Catch-all for other JWT errors
            return UserPydantic.anonymous_user()

    # Return anonymous user
    return UserPydantic.anonymous_user()


def create_access_token(data: dict) -> str:
    """Create a JWT access token with an expiration time."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.auth_token_age_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode,
                             config.auth_token_secret_key,
                             algorithm=config.auth_token_algorithm)
    return encoded_jwt


def create_token_cookie(token: str, token_type: str = "access") -> dict:
    """Create a cookie dictionary for the token."""
    max_age = timedelta(minutes=config.auth_token_age_minutes)

    cookie_data = {
        "key": f"{token_type}_token",
        "value": token,
        "httponly": True,
        "max_age": int(max_age.total_seconds()),
        "secure": True,
        "samesite": "lax",
    }

    return cookie_data
