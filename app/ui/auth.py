from fastapi import APIRouter, Request
from fastapi.responses import Response, HTMLResponse
from pydantic import ValidationError

from app.lib.config import get_app_config
from app.lib.security import hash_password, session_encode
from app.models.users import User, UserLoginForm, UserRegistrationForm

from app.ui.common import templates, error_response
from app.ui.common.session import flash_message


config = get_app_config()
router = APIRouter(tags=["auth"])


# Login page
@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html.j2", {"request": request})


# Login form submission
@router.post("/login", response_class=HTMLResponse)
async def login_post(request: Request):
    try:
        # Make user login form model from form data
        user_data = UserLoginForm(**await request.form()) # type:ignore

        # Authenticate user
        try:
            await user_data.authenticate()
        except ValueError as e:
            error_messages = [str(e)]
            return error_response(request, error_messages, status_code=401)

        # Get validated data
        data = user_data.model_dump()

    except ValidationError as e:
        error_messages = []

        for err in e.errors():
            error_messages.append(err['msg'])
            return error_response(request, error_messages, status_code=400)

    # Set login session
    user = await User.get(username=data.get("username"))
    request.session["user"] = session_encode(user.id, config.session_secret_key)

    # Set flash message and redirect
    flash_message(request, "Login successful!", "info")
    response = Response(status_code=200)
    response.headers["HX-Redirect"] = "/"

    return response


# Register page
@router.get("/register", response_class=HTMLResponse)
async def register(request: Request):
    return templates.TemplateResponse("register.html.j2", {"request": request})


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
@router.get("/logout")
async def logout():
    return {"message": "Logout endpoint"}

