from tortoise.fields import ReverseRelation
from typing import Annotated, Optional, TYPE_CHECKING
from pydantic import BaseModel, StringConstraints
from pathlib import Path
from tortoise import fields, models
from tortoise.exceptions import NoValuesFetched

from app.lib.config import get_app_config
from app.lib.helpers import MIME_TYPE_PATTERN

from app.models.common.base import TimestampMixin
from app.models.common.pagination import PaginationMixin
from app.models.users import User

if TYPE_CHECKING:
    from app.models.images import Image
    from tortoise.queryset import QuerySet


config = get_app_config()


# Validation patterns
EXTENSION_PATTERN = r'^[a-zA-Z0-9.-]{1,10}$'
CLEAN_FILENAME_PATTERN = r'[a-z0-9](?:[a-z0-9_]*[a-z0-9])?'
DATETIME_STAMP_PATTERN = r'\d{8}-\d{6}'
SHORT_UUID_PATTERN = r'[a-f0-9]{8}'
UNIQUE_FILENAME_PATTERN = rf'^{CLEAN_FILENAME_PATTERN}_{DATETIME_STAMP_PATTERN}_{SHORT_UUID_PATTERN}$'


def make_user_filepath(user_id: int, filename: str) -> Path:
    """Generate a user-specific file path."""
    user_dir = config.storage_path / f"user_{user_id}"

    # Ensure user directory exists
    user_dir.mkdir(exist_ok=True)
    if not user_dir.is_dir():
        raise ValueError(f"User directory {user_dir} is not a directory.")

    return user_dir / filename


class Upload(models.Model, TimestampMixin, PaginationMixin):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="uploads", on_delete=fields.RESTRICT)
    description = fields.CharField(max_length=255)
    name = fields.CharField(max_length=255)
    cleanname = fields.CharField(max_length=255)
    originalname = fields.CharField(max_length=255)
    ext = fields.CharField(max_length=10)
    size = fields.IntField()
    type = fields.CharField(max_length=255)
    extra = fields.CharField(max_length=32)
    viewed = fields.IntField(default=0)
    private = fields.IntField(default=0) # tinyint(1) in MySQL

    # Type hints for reverse relationships
    if TYPE_CHECKING:
        images: "QuerySet[Image]"

    class Meta:  # type: ignore[override]
        table = "uploads"

    class PydanticMeta:
        # Exclude fields that should not be included in the Pydantic model
        # - extra: Deprecated value which will be removed from the database model in a future revision
        # - user: A FK relationship which causes verbose output.  We already know the user (or can fetch it based on `user_id`)
        # - images.*: We don't need to include these values, we already know them as they are part of the `Upload` model
        exclude = [
            "extra",
            "user",
            "images.created_at",
            "images.updated_at",
            "images.id",
            "images.upload_id",
        ]

    @property
    def dot_ext(self) -> str:
        return f".{self.ext}" if self.ext else ""

    @property
    def filepath(self) -> Path:
        filename = f'{self.name}{self.dot_ext}'
        return make_user_filepath(getattr(self, "user_id"), filename)

    @property
    def filename(self) -> str:
        return f"{self.name}{self.dot_ext}"

    @property
    def url(self) -> str:
        url = f'{config.app_base_url}/get/{self.id}/{self.cleanname}{self.dot_ext}'
        return url

    @property
    def view_url(self) -> str:
        url = f'{config.app_base_url}/view/{self.id}/{self.cleanname}{self.dot_ext}'
        return url

    @property
    def download_url(self) -> str:
        url = f'{config.app_base_url}/download/{self.id}/{self.cleanname}{self.dot_ext}'
        return url
    
    @property
    def is_image(self) -> bool:
        """Return whether or not this file has related image metadata."""
        if hasattr(self, "images"):
            try:
                # If it behaves like a list (has len), it's fetched
                # ReverseRelation attempts to do this but raises NoValuesFetched if not loaded
                return len(self.images) > 0  # type: ignore[arg-type]
            except (TypeError, AttributeError, NoValuesFetched):
                # If it fails, it's likely a Relation manager or not fetched
                pass

            raise RuntimeError("Images relationship has not been fetched.")

        return False

    @property
    def is_private(self) -> bool:
        """Return whether or not this file is private."""
        return self.private == 1

    def is_owner(self, user: User) -> bool:
        """Return whether or not this file is owned by the current user."""
        return getattr(self, "user_id") == user.id


class UploadMetadata(BaseModel):
    """Metadata for an uploaded file."""

    # Related user
    user_id: int

    # Filename metadata
    filename: Annotated[str, StringConstraints(pattern=UNIQUE_FILENAME_PATTERN)]
    ext: Optional[Annotated[str, StringConstraints(pattern=EXTENSION_PATTERN, to_lower=True)]] = None
    original_filename: Annotated[str, StringConstraints(strip_whitespace=True)]
    clean_filename: Annotated[str, StringConstraints(pattern=rf'^{CLEAN_FILENAME_PATTERN}$')]
    
    # Computed metadata
    size: int
    mime_type: Annotated[str, StringConstraints(pattern=MIME_TYPE_PATTERN)]

    @property
    def dot_ext(self) -> str:
        return f".{self.ext}" if self.ext else ""

    @property
    def filepath(self) -> Path:
        filename = f'{self.filename}{self.dot_ext}'
        return make_user_filepath(self.user_id, filename)


class UploadResult(BaseModel):
    """Result of an upload operation."""

    status: str
    message: str
    upload_id: Optional[int]
    metadata: Optional[UploadMetadata]

    @property
    def url(self) -> str:
        """Generate the /get/ URL for this upload."""
        if self.upload_id and self.metadata:
            return f"{config.app_base_url}/get/{self.upload_id}/{self.metadata.clean_filename}{self.metadata.dot_ext}"
        return ""

    @property
    def view_url(self) -> str:
        """Generate the /view/ URL for this upload."""
        if self.upload_id and self.metadata:
            return f"{config.app_base_url}/view/{self.upload_id}/{self.metadata.clean_filename}{self.metadata.dot_ext}"
        return ""

    @property
    def download_url(self) -> str:
        """Generate the /download/ URL for this upload."""
        if self.upload_id and self.metadata:
            return f"{config.app_base_url}/download/{self.upload_id}/{self.metadata.clean_filename}{self.metadata.dot_ext}"
        return ""
