import jwt

from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError

from app.lib.config import get_app_config, logger
from app.lib.security import hash_password
from app.lib.auth import (
    get_current_user_from_request,
    set_token_cookies,
    delete_token_cookies,
    validate_refresh_token,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
)
from app.models.users import (
    User,
    UserPydantic,
    UserRegistrationForm,
    authenticate_user,
)

from app.ui.common import templates, error_response
from app.ui.common.session import flash_message


config = get_app_config()
router = APIRouter(tags=["auth"])


# Login page
@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse(request, "login.html.j2")


# Login form submission
@router.post("/login", response_class=HTMLResponse)
async def login_for_access_token(
    request: Request,
    form_data: Annotated[OAuth2PasswordRequestForm, Depends()],
):
    user = await authenticate_user(
        username=form_data.username,
        password=form_data.password,
    )
    if not user:
        error_messages = ["Invalid username or password"]
        return error_response(request, error_messages, status_code=401)

    # Set response status and cookies
    response = Response(status_code=200)

    # Update cookies
    await set_token_cookies(response, user)

    # Set flash message and redirect
    flash_message(request, "Login successful!", "info")
    response.headers["HX-Redirect"] = "/"
    return response


# Register page
@router.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse(request, "register.html.j2")


# Register form submission
@router.post("/register", response_class=HTMLResponse)
async def register_post(request: Request):
    # Create user registration form model from form data and handle validation
    try:
        user_data = UserRegistrationForm(**await request.form()) # type:ignore
        data = user_data.model_dump()
    except ValidationError as e:
        error_messages = []

        for err in e.errors():
            error_messages.append(err['msg'])

        response = templates.TemplateResponse(
            request=request,
            name="common/messages.html.j2",
            context={"error_messages": error_messages},
            status_code=400,
        )

        return response

    # Validate username
    # Check if user exists
    existing_user = await User.get_or_none(username=data.get("username"))
    if existing_user:
        error_message = "Username already exists"
        response = templates.TemplateResponse(
            request=request,
            name="common/messages.html.j2",
            context={"error_messages": [error_message]},
            status_code=400,
        )

        return response
    
    # Check if email address exists
    existing_user = await User.get_or_none(email=data.get("email"))
    if existing_user:
        error_message = "Email address already exists"
        response = templates.TemplateResponse(
            request=request,
            name="common/messages.html.j2",
            context={"error_messages": [error_message]},
            status_code=400,
        )

        return response
    
    # Generate password hash
    password = str(data.get("password"))
    password_hash = hash_password(password)

    # Create user in database
    new_user_data = {
        "username": data.get("username"),
        "email": data.get("email"),
        "password": password_hash,
        "remember_token": data.get("remember_token"),
    }
    new_user = await User.create(**new_user_data)
    await new_user.save()

    # Set flash message and redirect to login page
    flash_message(request, "Registration successful! Please log in.", "info")
    response = Response(status_code=201)
    response.headers["HX-Redirect"] = "/login"

    return response


# Logout endpoint
@router.get("/logout", response_class=RedirectResponse)
async def do_logout(request: Request,
                 current_user: User = Depends(get_current_user_from_request)):
    # Check if user is authenticated
    if current_user is None or current_user.id < 1:
        response = RedirectResponse(url="/", status_code=403)
        return response

    # Set flash message
    flash_message(request, "Logout successful.", "info")

    # Set up redirect response
    response = RedirectResponse(url="/", status_code=302)

    # Revoke refresh token
    try:
        refresh_token_payload = request.cookies.get("refresh_token")
        if refresh_token_payload:
            await revoke_refresh_token(refresh_token_payload, current_user.id)

    # Continue even if error occurs
    except Exception as e:
        logger.error("An error occured attempting to revoke refresh token.")
    
    # Delete cookies
    delete_token_cookies(response)

    return response


# Logout all endpoint
@router.get("/logout-all", response_class=RedirectResponse)
async def do_logout_all(request: Request,
                 current_user: User = Depends(get_current_user_from_request)):
    # Check if user is authenticated
    if current_user is None or current_user.id < 1:
        response = RedirectResponse(url="/", status_code=403)
        return response

    # Set flash message
    flash_message(request, "Logout successful.", "info")

    # Set up redirect response
    response = RedirectResponse(url="/", status_code=302)

    # Revoke refresh token
    try:
        await revoke_user_refresh_tokens(current_user.id)

    # Continue even if error occurs
    except Exception as e:
        logger.error("An error occured attempting to revoke refresh tokens.")
    
    # Delete cookies
    delete_token_cookies(response)

    return response


# Access token refresh endpoint
@router.post("/refresh", response_class=HTMLResponse)
async def refresh_access_token(request: Request):
    refresh_token = None

    # Get refresh token from cookie
    payload = request.cookies.get("refresh_token")
    if not payload:
        error_messages = ["Missing refresh token"]
        return error_response(request, error_messages, status_code=401)

    # Decode token to get user ID (don't need current_user dependency)
    try:
        decoded = jwt.decode(
            payload,
            config.auth_token_secret_key,
            algorithms=[config.auth_token_algorithm]
        )
        user_id = int(decoded.get("sub"))
    except (jwt.InvalidTokenError, ValueError, TypeError):
        error_messages = ["Invalid refresh token supplied"]
        return error_response(request, error_messages, status_code=401)

    # Get user
    current_user = await User.get_or_none(id=user_id)
    if not current_user:
        error_messages = ["User not found"]
        return error_response(request, error_messages, status_code=401)

    # Validate refresh token
    try:
        refresh_token = await validate_refresh_token(payload, user_id)

    except Exception as e:
        logger.error("An error occured attempting to refresh access token.")
        error_messages = ["Invalid refresh token supplied"]
        return error_response(request, error_messages, status_code=401)

    if refresh_token is None:
        logger.error("User refresh token validation failed.")
        error_messages = ["Invalid refresh token supplied"]
        return error_response(request, error_messages, status_code=401)
    
    # Set response status and cookies
    response = Response(status_code=200)
    await set_token_cookies(response, current_user, refresh_token)

    return response
