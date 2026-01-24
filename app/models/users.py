from datetime import datetime, timedelta
from typing_extensions import Self, Optional, Annotated, TYPE_CHECKING
from tortoise import fields, models
from pydantic import BaseModel, model_validator, EmailStr, StringConstraints
from email_validator import validate_email, EmailNotValidError

from app.lib.config import get_app_config
from app.lib.security import verify_password, generate_username

from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from tortoise.queryset import QuerySet
    from app.models.uploads import Upload


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
    
    # Type hints for reverse relationships
    if TYPE_CHECKING:
        uploads: "QuerySet[Upload]"

    class Meta:
        table = "users"
    
    @property
    async def images_count(self) -> int:
        """Return count of images owned by this user."""
        images_count = 0
        uploads = await self.uploads.all()
        for upload in uploads:
            upload_images_count = await upload.images.all().count()
            images_count += upload_images_count
        return images_count
    
    @property
    async def uploads_count(self) -> int:
        """Return count of uploads owned by this user."""
        uploads = await self.uploads.all().count()
        return uploads
    
    @property
    def max_uploads_count(self) -> int:
        """Return the maximum number of files allowed for this user."""
        if self.is_registered:
            return config.user_max_uploads
        else:
            return config.unregistered_max_uploads
    
    @property
    def max_file_size_mb(self) -> int:
        """Return the maximum file size allowed for this user in MB."""
        if self.is_registered:
            return config.user_max_file_size_mb
        else:
            return config.unregistered_max_file_size_mb
        
    @property
    def allowed_mime_types(self) -> list[str]:
        """Return the set of allowed MIME types for this user."""

        allowed_types: str
        if self.is_registered:
            allowed_types = config.user_allowed_types
        else:
            allowed_types = config.unregistered_allowed_types
        
        # Convert from comma-separated string to list
        allowed_types_list = allowed_types.split(',')

        # Sanitise list and remove empty entries
        allowed_types_list = [mime_type.strip().lower() for mime_type in allowed_types_list if mime_type.strip()]

        return allowed_types_list

    @classmethod
    async def generate_unique_username(cls, num_words: int = 2) -> str:
        """Generate a unique username not already in the database."""
        seq = 0

        while seq < 10:
            username = generate_username(num_words=num_words)
            existing_user = await cls.get_or_none(username=username)
            if not existing_user:
                return username
            
            seq += 1
            
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
    email: Annotated[EmailStr, StringConstraints(to_lower=True)]
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


async def mark_abandoned():
    """Clean up abandoned auto-created unregistered users"""
    abandoned_last_seen_cutoff = datetime.now() - timedelta(days=config.unregistered_account_abandonment_days)

    # Count and get abandoned users
    abandoned_users = await User.filter(
        is_registered=False,
        is_abandoned=False,
        last_seen_at__lt=abandoned_last_seen_cutoff,
    )
    abandoned_count = len(abandoned_users)

    # Mark users as abandoned
    for user in abandoned_users:
        user.is_abandoned = True
        user.fingerprint_hash = None # type: ignore
        await user.save()

    return abandoned_count
