from fastapi import APIRouter, Request
from fastapi.responses import Response, HTMLResponse
from pydantic import ValidationError

from app.models.users import User, UserRegistrationForm
from app.lib.security import hash_password

from app.ui.common import templates


router = APIRouter(tags=["auth"])


# Login page
@router.get("/login", response_class=HTMLResponse)
async def login(request: Request):
    return templates.TemplateResponse("login.html.j2", {"request": request})


# Login form submission
@router.post("/login")
async def login_post(request: Request):
    data = await request.form()

    return {"message": "Login endpoint"}


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

    response = Response(status_code=201)
    response.headers["HX-Redirect"] = "/login"

    return response

    
#    
#    # Create 

#    # Check if username is an email address
#    try:
#        username_email = EmailStr.validate(data.get("username"))
#    except ValueError:
#        username_email = None
#
#    if username_email is not None and data.get("email") != username_email:
#        return {"error": "When using an email as username, the email field must match"}
#    
#    # Validate email address
#    try:
#        EmailStr.validate(data.get("email"))
#    except ValueError:
#        return {"error": "Invalid email address"}
#
#    existing_user = await User.get_or_none(email=data.get("email"))
#    if existing_user:
#        return {"error": "Email already exists"}
#    
#    # Validate password (simple length check for now)
#    if len(str(data.get("password", ""))) < 8:
#        return {"error": "Password must be at least 8 characters long"}
#    
#    # Ensure password and password confirmation match
#    if data.get("password") != data.get("confirm_password"):
#        return {"error": "Password and confirmation do not match"}



#    return {"message": "Register endpoint"}


@router.get("/logout")
async def logout():
    return {"message": "Logout endpoint"}

