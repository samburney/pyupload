from tortoise import models, fields
from pydantic import BaseModel
from typing import Optional
from tortoise_serializer import Serializer

from app.models.common.base import TimestampMixin


class Image(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    upload = fields.ForeignKeyField("models.Upload", related_name="images", on_delete=fields.CASCADE)
    type = fields.CharField(max_length=255)
    width = fields.IntField()
    height = fields.IntField()
    bits = fields.IntField()
    channels = fields.IntField()

    class Meta:  # type: ignore[override]
        table = "images"


class ImageSerializer(Serializer):
    """Serializer for the Image model."""

    # Model fields
    id: int
    upload_id: int
    type: str
    width: int
    height: int
    bits: int
    channels: int


class ImageMetadata(BaseModel):
    """Metadata for an uploaded file."""

    # Related upload
    upload_id: int

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
