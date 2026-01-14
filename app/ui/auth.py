from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import Response, HTMLResponse, RedirectResponse
from fastapi.security import OAuth2PasswordRequestForm
from pydantic import ValidationError

from app.lib.config import get_app_config
from app.lib.security import hash_password
from app.lib.auth import create_access_token, create_token_cookie
from app.models.users import User, UserRegistrationForm, authenticate_user

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

    # Make login token and set to cookie
    access_token = create_access_token(
        data={"sub": user.username} # type: ignore
    )
    access_token_cookie = create_token_cookie(token=access_token, token_type="access")
    response = Response(status_code=200)
    response.set_cookie(**access_token_cookie)

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
async def logout(request: Request):
    # Set flash message
    flash_message(request, "Logout successful.", "info")

    # Delete access token cookie and redirect
    response = RedirectResponse(url="/", status_code=302)
    response.delete_cookie(key="access_token")

    return response
