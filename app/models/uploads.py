import re

from typing import Annotated, Optional, TYPE_CHECKING
from pydantic import BaseModel, StringConstraints, ConfigDict
from tortoise import fields, models
from pathlib import Path

from app.lib.config import get_app_config
from app.lib.helpers import MIME_TYPE_PATTERN

from app.models.base import TimestampMixin

if TYPE_CHECKING:
    from tortoise.queryset import QuerySet
    from app.models.images import Image


config = get_app_config()


# Validation patterns
EXTENSION_PATTERN = r'^[a-zA-Z0-9.-]{1,10}$'
CLEAN_FILENAME_PATTERN = r'[a-z0-9](?:[a-z0-9_]*[a-z0-9])?'
DATETIME_STAMP_PATTERN = r'\d{8}-\d{6}'
SHORT_UUID_PATTERN = r'[a-f0-9]{8}'
UNIQUE_FILENAME_PATTERN = rf'^{CLEAN_FILENAME_PATTERN}_{DATETIME_STAMP_PATTERN}_{SHORT_UUID_PATTERN}$'

class Upload(models.Model, TimestampMixin):
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

    class Meta:
        table = "uploads"


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
    def filepath(self) -> Path:
        """Generate a user-specific file path."""

        user_dir = config.storage_path / f"user_{self.user_id}"

        # Ensure user directory exists
        user_dir.mkdir(exist_ok=True)
        if not user_dir.is_dir():
            raise ValueError(f"User directory {user_dir} is not a directory.")

        return user_dir / self.filename

class UploadResult(BaseModel):
    """Result of an upload operation."""

    model_config = ConfigDict(arbitrary_types_allowed=True)

    status: str
    message: str
    upload: Optional[Upload]
    metadata: Optional[UploadMetadata]
