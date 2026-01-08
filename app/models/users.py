from typing_extensions import Self
from tortoise import fields, models
from pydantic import BaseModel, ValidationInfo, model_validator, EmailStr
from email_validator import validate_email, EmailNotValidError

from app.models.base import TimestampMixin


# User database model
class User(models.Model, TimestampMixin):
    id = fields.IntField(pk=True)
    username = fields.CharField(max_length=64)
    email = fields.CharField(max_length=255)
    password = fields.CharField(max_length=60)
    remember_token = fields.CharField(max_length=100)

    class Meta:
        table = "users"

# Pydantic models for Users
# Base User model
class UserPydantic(BaseModel):
    username: str
    email: EmailStr
    remember_token: str = ""

    @model_validator(mode='after')
    def check_email_username(self) -> Self:
        # Check if username is a valid email
        try:
            username_email_info = validate_email(self.username,
                                                 check_deliverability=False)

            # Check if email field matches username
            if self.email != username_email_info.email:
                raise ValueError('When using an email as username, the email field must match')

            return self

        except EmailNotValidError:
            # Username is not an email, which is acceptable
            return self


# User registration form model
class UserRegistrationForm(UserPydantic):
    password: str
    confirm_password: str

    # Validator to confirm password and confirmation match
    @model_validator(mode='after')
    def check_passwords_match(self) -> Self:
        if self.password is not None:
            if self.password != self.confirm_password:
                raise ValueError('Passwords do not match')
        
        return self

    # Ensure password meets minimum length
    @model_validator(mode='after')
    def check_password_length(self) -> Self:
        if self.password is not None:
            if len(self.password) < 8:
                raise ValueError('Password must be at least 8 characters long')
        
        return self
