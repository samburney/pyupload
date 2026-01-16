from datetime import datetime, timezone, timedelta

from typing_extensions import Self
from tortoise import fields, models
from pydantic import BaseModel, model_validator, EmailStr
from email_validator import validate_email, EmailNotValidError

from app.lib.config import get_app_config
from app.lib.security import verify_password
from app.models.base import TimestampMixin


config = get_app_config()


# User database model
class User(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    username = fields.CharField(max_length=64)
    email = fields.CharField(max_length=255)
    password = fields.CharField(max_length=60)
    remember_token = fields.CharField(max_length=100)

    class Meta:
        table = "users"

# Refresh Token database model
class RefreshToken(models.Model, TimestampMixin):
    """Model for storing JWT refresh tokens with revocation support."""
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="refresh_tokens", on_delete=fields.CASCADE)
    token_hash = fields.CharField(max_length=64, db_index=True)  # SHA256 hash (64 hex chars)
    expires_at = fields.DatetimeField()
    revoked = fields.BooleanField(default=False)

    class Meta:
        table = "refresh_tokens"

    async def revoke(self) -> bool:
        """Revoke this refresh token."""
        self.revoked = True
        await self.save()
        return True

    def is_valid(self) -> bool:
        """Check if this token is valid (not expired, not revoked, not deleted).
        
        Returns:
            True if valid, False otherwise
        """
        now = datetime.now(timezone.utc)
        return (
            not self.revoked
            and self.expires_at > now
        )

    @classmethod
    async def revoke_all_for_user(
        cls,
        user_id: int
    ) -> int:
        """Revoke all refresh tokens for a specific user.
        
        Useful for logout-all or security scenarios.
        
        Args:
            user_id: The user's ID
            
        Returns:
            Number of tokens revoked
        """
        tokens = await cls.filter(
            user_id=user_id,
            revoked=False
        ).all()
        
        for token in tokens:
            token.revoked = True
            await token.save()
        
        return len(tokens)

    @classmethod
    async def cleanup_expired(cls) -> int:
        """Delete expired refresh tokens.
        
        Should be run periodically as a maintenance task.
        
        Returns:
            Number of tokens deleted
        """
        now = datetime.now(timezone.utc)
        expired_tokens = await cls.filter(expires_at__lt=now).all()
        
        count = len(expired_tokens)
        for token in expired_tokens:
            await token.delete()
        
        return count

# Pydantic models for Users
# Base User model
class UserPydanticBase(BaseModel):
    username: str
    remember_token: str = ""

# User model for general use
class UserPydantic(UserPydanticBase):
    id: int
    email: EmailStr
    is_authenticated: bool = False

    @classmethod
    async def from_tortoise_orm(cls, user: User) -> Self:
        """Create UserPydantic from Tortoise ORM User model."""
        return cls(
            id=user.id,
            username=user.username,
            email=user.email,
            remember_token=user.remember_token,
        )
    
    @classmethod
    def anonymous_user(cls) -> Self:
        return cls(
            id=-1,
            username='anonymous',
            email=f'anonymous@{config.app_default_domain}',
            remember_token='',
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
