import jwt
import hashlib

from datetime import datetime, timedelta, timezone
from fastapi import Request, Response
from tortoise.exceptions import IntegrityError, OperationalError

from app.lib.config import get_app_config, logger

from app.models.users import User, UserPydantic, RefreshToken


config = get_app_config()


async def get_current_user(request: Request) -> None | User | UserPydantic:
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
                if user is not None:
                    return user

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


async def set_token_cookies(request: Request,
                            response: Response,
                            user: User,
                            refresh_token: RefreshToken | None = None) -> None:
    # Handle access token
    access_token_payload = create_access_token(
        data={"sub": user.username} # type: ignore
    )
    access_token_cookie = create_token_cookie(token=access_token_payload, token_type="access")
    response.set_cookie(**access_token_cookie)

    # Handle refresh token
    refresh_token_payload = create_refresh_token(user)
    try:
        # If existing refresh token not provided, store a new one
        if refresh_token is None:
            await store_refresh_token(refresh_token_payload, user)
        
        # Otherwise rotate existing refresh token
        else:
            refresh_token.update_from_dict({
                "token_hash": hashlib.sha256(refresh_token_payload.encode('utf-8')).hexdigest(),
                "expires_at": datetime.now(timezone.utc) + timedelta(days=config.auth_refresh_token_age_days),
            })
            await refresh_token.save()
        
        # Update refresh token cookie
        refresh_token_cookie = create_token_cookie(token=refresh_token_payload, token_type="refresh")
        response.set_cookie(**refresh_token_cookie)
    except (jwt.InvalidTokenError, IntegrityError, OperationalError) as e:
        # Errors already logged by store_refresh_token method.
        pass


def delete_token_cookies(response: Response) -> None:
    """Delete access and refresh token cookies from the response."""
    response.delete_cookie("access_token")
    response.delete_cookie("refresh_token")


def create_access_token(data: dict) -> str:
    """Create a JWT access token with an expiration time."""
    to_encode = data.copy()
    expire = datetime.now(timezone.utc) + timedelta(minutes=config.auth_token_age_minutes)
    to_encode.update({"exp": expire})
    encoded_jwt = jwt.encode(to_encode,
                             config.auth_token_secret_key,
                             algorithm=config.auth_token_algorithm)
    return encoded_jwt


def create_refresh_token(user: User) -> str:
    """Create a JWT refresh token from a User instance."""
    expire = datetime.now(timezone.utc) + timedelta(days=config.auth_refresh_token_age_days)
    to_encode = {
        "sub": str(user.id),
        "exp": expire,
    }
    encoded_jwt = jwt.encode(to_encode,
                             config.auth_token_secret_key,
                             algorithm=config.auth_token_algorithm)
    return encoded_jwt


def create_token_cookie(token: str, token_type: str = "access") -> dict:
    """Create a cookie dictionary for the token."""
    if token_type not in ["access", "refresh"]:
        raise ValueError("Invalid token type specified")

    if token_type == "access":
        max_age = timedelta(minutes=config.auth_token_age_minutes)
    elif token_type == "refresh":
        max_age = timedelta(days=config.auth_refresh_token_age_days)

    cookie_data = {
        "key": f"{token_type}_token",
        "value": token,
        "httponly": True,
        "max_age": int(max_age.total_seconds()),
        "secure": True,
        "samesite": "lax",
    }

    return cookie_data


async def store_refresh_token(token: str, user: User) -> RefreshToken:
    """Stored hashed refresh token in the database."""

    # Get token expiration from JWT payload
    try:
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        exp_timestamp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        # Calculate token hash
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()
    except jwt.InvalidTokenError:
        raise ValueError("Invalid JWT token provided")

    # Store in database
    try:
        refresh_token = await RefreshToken.create(
            user=user,
            token_hash=token_hash,
            expires_at=expires_at,
            revoked=False,
        )
    except (IntegrityError, OperationalError) as e:
        # Log the error for monitoring
        logger.error(f"Database error storing refresh token for user {user.id}: {e}")
        # Re-raise - let the caller decide how to handle
        raise

    return refresh_token


async def validate_refresh_token(token: str, user: User | int) -> RefreshToken | None:
    """Validate a refresh token against the database.
    
    Values
      token (str): Refresh token to be validated
      user: (User | int): A `User` model instance or `user.id`

    Returns the RefreshToken instance if valid, else None.
    """
    try:
        # Decode token to get expiration
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        exp_timestamp = payload.get("exp")
        expires_at = datetime.fromtimestamp(exp_timestamp, tz=timezone.utc)

        # Check expiration
        if expires_at < datetime.now(timezone.utc):
            return None

        # Calculate token hash
        token_hash = hashlib.sha256(token.encode('utf-8')).hexdigest()

        # Look up in database
        refresh_token = await RefreshToken.get_or_none(
            user=user,
            token_hash=token_hash,
            revoked=False,
            expires_at__gt=datetime.now(timezone.utc)
        )
        return refresh_token

    except jwt.InvalidTokenError:
        return None


async def revoke_refresh_token(token: str, user: User | int) -> bool:
    """Revoke a refresh token in the database."""
    try:
        refresh_token = await validate_refresh_token(token, user)
        if refresh_token:
            return await refresh_token.revoke()

    # Catch database errors
    except (IntegrityError, OperationalError) as e:
        # Log the error for monitoring
        logger.error(f"Database error revoking refresh token: {e}")
        # Re-raise - let the caller decide how to handle
        raise

    return False


async def revoke_user_refresh_tokens(user: User | int) -> int:
    """Revoke all refresh tokens for a user."""
    # Set user_id prior to possible user fetch
    if isinstance(user, int):
        user_id = user

    # Revoke all non-revoked tokens
    try:
        # Get User instance if only user.id provided
        if isinstance(user, int):
            user = await User.get_or_none(id=user) # type: ignore
            if user is None:
                return 0

        # Revoke all active user tokens
        return await RefreshToken.revoke_all_for_user(user.id) # type: ignore

    # Catch database errors
    except (IntegrityError, OperationalError) as e:
        # Log the error for monitoring
        logger.error(f"Database error revoking refresh tokens for user {user_id}: {e}")
        # Re-raise - let the caller decide how to handle
        raise
