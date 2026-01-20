import jwt
import hashlib

from datetime import datetime, timedelta, timezone
from fastapi import Request, Response
from tortoise.exceptions import IntegrityError, OperationalError

from app.lib.config import get_app_config, logger
from app.lib.security import (
    extract_fingerprint_data,
    generate_fingerprint_hash,
    get_request_ip,
)

from app.models.users import User
from app.models.refresh_tokens import RefreshToken


config = get_app_config()


async def get_current_user_from_request(request: Request) -> None | User | UserPydantic:
    """Dependency to get the current authenticated user from the session."""
    
    # Validate access token from cookie
    access_token = request.cookies.get("access_token")
    if not access_token:
        return None
    
    return await get_current_user_from_token(access_token)


async def get_current_user_from_token(token: str) -> None | User | UserPydantic:
    """Get the current authenticated user from the access token."""
    try:
        # Decode JWT token
        payload = jwt.decode(
            token,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        username: str = payload.get("sub")
        if username is None:
            return None

        # Get user instance
        user = await User.get_or_none(
            username=username,
            is_disabled=False,
            is_abandoned=False,
        )

        # Attempt to get by user.id if username lookup failed and is numeric
        if user is None and username.isnumeric():
            user = await User.get_or_none(
                id=int(username),
                is_disabled=False,
                is_abandoned=False,
            )
        return user

    except jwt.InvalidTokenError:
        return None


async def get_current_user_from_refresh_token(request: Request) -> User | None:
    """Get the current authenticated user from the refresh token."""
    # Get refresh token from header or cookie
    payload = get_refresh_token_payload(request)
    if payload is None:
        return None
    
    # Get current user from refresh token payload
    current_user = await get_current_user_from_token(payload)
    if current_user is None or not isinstance(current_user, User):
        return None

    return current_user


async def get_current_authenticated_user(request: Request) -> User | None:
    """Dependency to get the current authenticated user or redirect to login page."""
    current_user = await get_current_user_from_request(request)

    if current_user is None or not isinstance(current_user, User):
        return None

    return current_user


async def set_token_cookies(response: Response,
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
            await update_stored_refresh_token(
                refresh_token=refresh_token,
                refresh_token_payload=refresh_token_payload,
                user=user
            )
        
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


async def create_and_store_refresh_token(user: User) -> str:
    """Create and store a refresh token for the user."""
    refresh_token_payload = create_refresh_token(user)
    try:
        # Store in database
        await store_refresh_token(refresh_token_payload, user)
    except (jwt.InvalidTokenError, IntegrityError, OperationalError) as e:
        # Errors already logged by store_refresh_token method.
        raise

    return refresh_token_payload


async def update_stored_refresh_token(refresh_token: RefreshToken,
                                      refresh_token_payload: str,
                                      user: User) -> RefreshToken:
    """Update an existing stored refresh token with a new token value."""
    # Update stored token hash and expiration
    refresh_token.update_from_dict({
        "token_hash": hashlib.sha256(refresh_token_payload.encode('utf-8')).hexdigest(),
        "expires_at": datetime.now(timezone.utc) + timedelta(days=config.auth_refresh_token_age_days),
    })
    await refresh_token.save()
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


def get_refresh_token_payload(request: Request) -> str | None:
    """Get the refresh token payload from the request headers or cookies."""
    # Check Authorization header first
    auth_header = request.headers.get("Authorization")
    if auth_header and auth_header.startswith("Bearer "):
        return auth_header.split(" ", 1)[1]
    
    # Fallback to cookie
    return request.cookies.get("refresh_token")


async def get_unregistered_user_by_fingerprint(request: Request) -> User | None:
    """Get an unregistered user by client fingerprint."""
    
    # Get fingerprint hash
    fingerprint_hash = generate_fingerprint_hash(request)

    # Attempt to find existing unregistered user by fingerprint hash
    existing_user = await User.get_or_none(
        fingerprint_hash=fingerprint_hash,
        is_registered=False,
        is_abandoned=False,
        is_disabled=False,
    )
    return existing_user


async def get_or_create_unregistered_user(request: Request) -> User:
    """
    Using client fingerprint, get matching unregistered user or create a new
     one.
    """
    
    # Check for existing unregistered user by fingerprint
    existing_user = await get_unregistered_user_by_fingerprint(request)
    if existing_user is not None:
        return existing_user
    
    # Create new unregistered user
    fingerprint_data = extract_fingerprint_data(request)
    fingerprint_hash = generate_fingerprint_hash(request)

    new_user_data = {
        "username": await User.generate_unique_username(),
        "email": "",
        "password": "",
        "is_registered": False,
        "fingerprint_hash": fingerprint_hash,
        "fingerprint_data": fingerprint_data,
        "registration_ip": str(get_request_ip(request)) if get_request_ip(request) else None,
    }

    new_user = await User.create(**new_user_data)
    
    return new_user
