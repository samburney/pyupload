from fastapi import Request, Response

import app.lib.auth as lib_auth

from app.models.users import User

from app.ui.common.session import flash_message


class LoginRequiredException(Exception):
    """Exception raised when user is not authenticated."""
    pass

class UnauthorizedException(Exception):
    """Exception raised when user is not authorized."""
    pass


async def get_current_user(request: Request) -> User:
    """Dependency to get the current authenticated user."""
    current_user = await lib_auth.get_current_user_from_request(request)

    # Check if user is over quota
    if current_user:
        await check_user_over_quota(request, current_user)

    return current_user


async def get_current_authenticated_user(request: Request) -> User:
    """Dependency to get the current authenticated user."""
    current_user = await lib_auth.get_current_user_from_request(request)

    # If no user is authenticated, raise exception
    if current_user is None or not isinstance(current_user, User):
        raise LoginRequiredException("User is not authenticated.")

    # Check if user is over quota
    await check_user_over_quota(request, current_user)

    return current_user


async def get_current_registered_user(request: Request) -> User:
    """Dependency to require the current authenticated user to be registered."""

    # Get currently authenticated users
    current_user = await get_current_authenticated_user(request)

    # Ensure user is registered
    if not current_user.is_registered:
        raise UnauthorizedException("Registered user required.")

    # Check if user is over quota
    await check_user_over_quota(request, current_user)

    return current_user


async def get_or_create_authenticated_user(request: Request) -> User:
    """
    Dependency to get the current authenticated user.
    
    If no user is authenticated, create an unregistered user and return it.
    """
    current_user = await lib_auth.get_current_user_from_request(request)

    # If no user is authenticated, create and return an unregistered user
    if current_user is None or not isinstance(current_user, User):
        current_user = await lib_auth.get_or_create_unregistered_user(request)

    # Check if user is over quota
    await check_user_over_quota(request, current_user)

    return current_user


async def check_user_over_quota(request: Request, current_user: User) -> None:
    """Check if the current authenticated user is over quota."""
    if await current_user.uploads_count >= current_user.max_uploads_count:
        if current_user.is_registered:
            flash_message(request, "You are over your upload quota, you will no longer be able to upload files until you remove some files.", "error")
        else:
            flash_message(request, "You are over your upload quota. Please register to increase your quota.", "error")
