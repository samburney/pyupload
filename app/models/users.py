from typing_extensions import Self, Optional
from tortoise import fields, models
from pydantic import BaseModel, model_validator, EmailStr
from email_validator import validate_email, EmailNotValidError

from app.lib.config import get_app_config
from app.lib.security import verify_password, generate_username
from app.models.base import TimestampMixin


config = get_app_config()


# User database model
class User(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    username = fields.CharField(max_length=64)
    email = fields.CharField(max_length=255)
    password = fields.CharField(max_length=60)
    is_registered = fields.BooleanField(default=False)
    is_abandoned = fields.BooleanField(default=False)
    is_admin = fields.BooleanField(default=False)
    is_disabled = fields.BooleanField(default=False)
    fingerprint_hash = fields.CharField(max_length=64, null=True, db_index=True)
    fingerprint_data = fields.JSONField(null=True)
    registration_ip = fields.CharField(max_length=45, null=True)
    last_login_ip = fields.CharField(max_length=45, null=True)
    last_seen_at = fields.DatetimeField(null=True)

    class Meta:
        table = "users"
    
    @property
    async def items_count(self) -> int:
        """Return count of items owned by this user."""
        images = await self.images_count
        uploads = await self.uploads_count
        return images + uploads
    
    @property
    async def images_count(self) -> int:
        """Return count of images owned by this user."""
        # Placeholder for now, will list owned items in `images` table.
        return 0
    
    @property
    async def uploads_count(self) -> int:
        """Return count of images owned by this user."""
        # Placeholder for now, will list owned items in `uploads` table.
        return 0


    @classmethod
    async def generate_unique_username(cls, num_words: int = 2) -> str:
        """Generate a unique username not already in the database."""
        seq = 0

        while seq < 10:
            username = generate_username(num_words=num_words)
            existing_user = await cls.get_or_none(username=username)
            if not existing_user:
                return username
            
        raise ValueError("Failed to generate a unique username after multiple attempts.")


# Pydantic models for Users
# Base User model
class UserPydanticBase(BaseModel):
    username: str

# User model for general use
class UserPydantic(UserPydanticBase):
    id: int
    email: Optional[EmailStr]
    is_authenticated: bool = False

    @classmethod
    async def from_tortoise_orm(cls, user: User) -> Self:
        """Create UserPydantic from Tortoise ORM User model."""
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
        )
    
    @classmethod
    def anonymous_user(cls) -> Self:
        return cls(
            id=-1,
            username='anonymous',
            email=f'anonymous@{config.app_default_domain}',
        )


# User login form model
class UserLoginForm(UserPydanticBase):
    password: str
    remember_login: bool = False

    # Authenticate user against database
    async def authenticate(self):
        # Confirm user exists
        user = await User.get_or_none(username=self.username)
        if not user:
            raise ValueError('Invalid username or password')

        # Verify password
        valid_password = verify_password(
            self.password,
            user.password,
        )
        if not valid_password:
            raise ValueError('Invalid username or password')

        return self

# User registration form model
class UserRegistrationForm(UserPydanticBase):
    email: EmailStr
    password: str
    confirm_password: str

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


async def authenticate_user(username: str, password: str):
    """Return authenticated User instance"""
    user = await User.get_or_none(username=username) or await User.get_or_none(email=username)

    if user and verify_password(plain_password=password, hashed_password=user.password):
        return user
    else:
        return None
