from typing import Annotated, Optional, TYPE_CHECKING
from pydantic import BaseModel, StringConstraints
from tortoise import fields, models
from pathlib import Path

from app.lib.config import get_app_config
from app.lib.helpers import MIME_TYPE_PATTERN

from app.models.common.base import TimestampMixin
from app.models.common.pagination import PaginationMixin

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
        url = f'/get/{self.id}/{self.cleanname}{self.dot_ext}'
        return url

    @property
    def download_url(self) -> str:
        url = f'/download/{self.id}/{self.cleanname}{self.dot_ext}'
        return url
    
    @property
    def is_image(self) -> bool:
        """Return whether or not this file has related image metadata."""
        if hasattr(self, "images") and self.images.exists():
            return True
        return False
        

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
