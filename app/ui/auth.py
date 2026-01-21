import jwt

from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError

from app.lib.config import get_app_config, logger
from app.lib.security import hash_password, get_request_ip
from app.lib.auth import (
    get_current_user_from_request,
    set_token_cookies,
    delete_token_cookies,
    revoke_refresh_token,
    revoke_user_refresh_tokens,
)
from app.models.users import (
    User,
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
    return templates.TemplateResponse(request, "auth/login.html.j2")


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
    # Check for existing user session
    current_user = await get_current_user_from_request(request)

    # Redirect to home page if user is already registered
    if current_user and (current_user.is_registered or current_user.is_abandoned or current_user.is_disabled):
        flash_message(request, "You are already registered and logged in.", "info")
        response = RedirectResponse(url="/", status_code=302)
        return response
    elif current_user and not current_user.is_registered:
        flash_message(request, "The registration form has been pre-filled with your username, change it if you wish.", "info")

    return templates.TemplateResponse(request, "auth/register.html.j2", context={"current_user": current_user})


# Register form submission
@router.post("/register", response_class=HTMLResponse)
async def register_post(request: Request):
    # Check for existing user session
    current_user = await get_current_user_from_request(request)

    # Redirect to home page if user is already registered
    if current_user and (current_user.is_registered or current_user.is_abandoned or current_user.is_disabled):
        flash_message(request, "You are already registered and logged in.", "info")
        response = RedirectResponse(url="/", status_code=302)
        return response

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
            name="layout/messages.html.j2",
            context={"error_messages": error_messages},
            status_code=400,
        )

        return response

    # Validate username
    existing_user = await User.get_or_none(username=data.get("username"))
    if existing_user and existing_user.id != (current_user.id if current_user else 0):
        error_message = "Username already exists"
        response = templates.TemplateResponse(
            request=request,
            name="layout/messages.html.j2",
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
            name="layout/messages.html.j2",
            context={"error_messages": [error_message]},
            status_code=400,
        )

        return response
    
    # Generate password hash
    password = str(data.get("password"))
    password_hash = hash_password(password)

    # New user registration
    new_user_data = {
        "username": data.get("username"),
        "email": data.get("email"),
        "password": password_hash,
        "remember_token": data.get("remember_token"),
        "is_registered": True,
        "fingerprint_hash": None,
        "fingerprint_data": None,
        "registration_ip": str(get_request_ip(request)) if get_request_ip(request) else None
    }

    # Create new user
    if not current_user:
        new_user = await User.create(**new_user_data)
        await new_user.save()

    # Upgrade existing unregistered user
    else:
        current_user.update_from_dict(new_user_data)
        current_user.is_registered = True
        await current_user.save()

    # Set flash message and redirect to login page
    flash_message(request, "Registration successful! Please log in.", "info")
    response = Response(status_code=201)
    response.headers["HX-Redirect"] = "/login"

    # Invalidate existing session to force a new login
    if current_user:
        # Revoke refresh token
        try:
            await revoke_user_refresh_tokens(current_user.id)

        # Continue even if error occurs
        except Exception as e:
            logger.error("An error occured attempting to revoke refresh tokens.")
        
        # Delete cookies
        delete_token_cookies(response)

    return response


# Logout endpoint
@router.get("/logout", response_class=RedirectResponse)
async def do_logout(request: Request,
                 current_user: User = Depends(get_current_user_from_request)):
    # Check if user is authenticated
    if current_user is None or current_user.id < 1:
        response = RedirectResponse(url="/", status_code=303)
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
    if current_user is None or current_user.id < 1:  # FIXME: Adjust check as needed
        response = RedirectResponse(url="/", status_code=303)
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
