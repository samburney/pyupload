from tortoise import models, fields
from pydantic import BaseModel, StringConstraints, ConfigDict
from typing import Annotated, Optional

from app.models.base import TimestampMixin
from app.models.uploads import Upload


class Image(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    upload = fields.ForeignKeyField("models.Upload", related_name="images", on_delete=fields.CASCADE)
    type = fields.CharField(max_length=255)
    width = fields.IntField()
    height = fields.IntField()
    bits = fields.IntField()
    channels = fields.IntField()

    class Meta:
        table = "images"


class ImageMetadata(BaseModel):
    """Metadata for an uploaded file."""

    # Allow arbitrary types
    model_config = ConfigDict(arbitrary_types_allowed=True)

    # Related upload
    upload: Upload

    # Computed metadata
    type: str
    width: int
    height: int
    bits: int
    channels: int

    # Additional optional metadata not yet supported by database
    animated: Optional[bool] = None
    frames: Optional[int] = None
    transparency: Optional[bool] = None
