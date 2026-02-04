import jwt

from typing import Annotated
from fastapi import (
    APIRouter, Depends, status, HTTPException, Request, Response
)
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from pydantic import BaseModel

from app.lib.config import get_app_config
from app.lib.auth import (
    get_current_user_from_token,
    create_access_token,
    create_refresh_token,
    create_and_store_refresh_token,
    update_stored_refresh_token,
    create_token_cookie,
    delete_token_cookies,
    validate_refresh_token,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
    get_refresh_token_payload,
    get_current_user_from_refresh_token,
)
from app.models.users import User, authenticate_user


config = get_app_config()
router = APIRouter(tags=["auth"])
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="api/v1/login")

# Exceptions for invalid credentials
credentials_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate credentials",
    headers={"WWW-Authenticate": "Bearer"},
)
invalid_token_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Could not validate token",
    headers={"WWW-Authenticate": "Bearer"},
)
invalid_user_exception = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid user session",
    headers={"WWW-Authenticate": "Bearer"},
)


class Token(BaseModel):
    """Model for access token response."""
    access_token: str
    token_type: str


async def get_current_user(token: Annotated[str, Depends(oauth2_scheme)]):
    """Get the current active user from the token."""
    user = await get_current_user_from_token(token=token)
    if user is None:
        raise credentials_exception
    return user


# Login endpoint
@router.post("/login")
async def login_for_access_token(
    response: Response,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
) -> Token:
    """Authenticate user and return access token."""

    # Get authenticated user instance
    user = await authenticate_user(
        username=form_data.username,
        password=form_data.password,
    )
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Incorrect username or password",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # Create access token
    token_data = {
        "sub": str(user.username)
    }
    access_token = create_access_token(data=token_data)
    refresh_token = await create_and_store_refresh_token(user)
    

    # Set token cookies
    access_token_cookie_data = create_token_cookie(access_token, 'access')
    refresh_token_cookie_data = create_token_cookie(refresh_token, 'refresh')
    response.set_cookie(**access_token_cookie_data)
    response.set_cookie(**refresh_token_cookie_data)

    # Return token
    return Token(access_token=access_token, token_type="bearer")


# Logout endpoint
@router.post("/logout")
async def do_logout(request: Request, response: Response) -> dict:
    """Logout the current user session."""

    # Get refresh token payload
    refresh_token_payload = get_refresh_token_payload(request)
    if not refresh_token_payload:
        raise invalid_token_exception

    # Get current_user from refresh token
    current_user = await get_current_user_from_refresh_token(request)
    if current_user is None or current_user.id < 1:
        raise invalid_user_exception

    # Revoke refresh token and delete cookies
    await revoke_refresh_token(refresh_token_payload, current_user.id)
    delete_token_cookies(response)

    return {"detail": "Successfully logged out."}


# Logout all endpoint
@router.post("/logout-all")
async def do_logout_all(request: Request, response: Response) -> dict:
    """Logout the current user from all sessions."""

    # Get current_user from refresh token
    current_user = await get_current_user_from_refresh_token(request)
    if current_user is None or current_user.id < 1:
        raise invalid_user_exception

    # Revoke all refresh tokens for user
    await revoke_user_refresh_tokens(current_user.id)
    
    # Delete cookies
    delete_token_cookies(response)

    return {"detail": "Successfully logged out from all sessions."}


# Access token refresh endpoint
@router.post("/refresh")
async def refresh_access_token(request: Request, response: Response) -> Token:
    """Refresh the access token using a valid refresh token and return it."""

    # Get refresh token payload
    old_refresh_token = get_refresh_token_payload(request)
    if not old_refresh_token:
        raise invalid_token_exception

    # Get current_user from refresh token
    current_user = await get_current_user_from_refresh_token(request)
    if current_user is None or current_user.id < 1:
        raise invalid_user_exception

    # Validate refresh token
    refresh_token = await validate_refresh_token(old_refresh_token, current_user.id)
    if not refresh_token:
        raise invalid_token_exception

    # Create new access and refresh tokens
    token_data = {
        "sub": str(current_user.username)
    }
    access_token_payload = create_access_token(data=token_data)
    new_refresh_token = create_refresh_token(current_user)
    await update_stored_refresh_token(
        refresh_token=refresh_token,
        refresh_token_payload=new_refresh_token,
        user=current_user
    )

    # Update token cookies
    access_token_cookie_data = create_token_cookie(access_token_payload, 'access')
    response.set_cookie(**access_token_cookie_data)
    refresh_token_cookie_data = create_token_cookie(new_refresh_token, 'refresh')
    response.set_cookie(**refresh_token_cookie_data)

    # Return new access token
    return Token(access_token=access_token_payload, token_type="bearer")


@router.get("/users/me")
async def read_users_me(
    current_user: Annotated[User, Depends(get_current_user)],
):
    return current_user
