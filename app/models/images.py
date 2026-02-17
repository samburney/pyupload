from tortoise import models, fields
from pydantic import BaseModel
from typing import Optional
from tortoise_serializer import Serializer

from app.lib.helpers import IMAGE_FORMATS, IMAGE_PROCESSING_FORMATS, IMAGE_CONVERSION_DST_FORMATS, IMAGE_SHORT_DIMENSIONS

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

    @property
    def supports_processing(self) -> bool:
        """Whether this image supports additional processing (resizing, format conversion)."""
        if f".{self.type}" in IMAGE_PROCESSING_FORMATS:
            return True
        return False


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

    # Computed properties
    supports_processing: bool


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


class ProcessedImageMetadata(ImageMetadata):
    """Metadata for a processed image variant."""

    # Metadata related to an image variant
    requested_props: dict
    mime_type: Optional[str] = None
    new_type: Optional[str] = None
    new_mime_type: Optional[str] = None
    resized: bool

    @property
    def converted(self) -> bool:
        """Whether the image was converted to a new format (e.g. from PNG to JPEG)."""
        if self.new_mime_type is not None and self.mime_type is not None:
            return self.new_mime_type != self.mime_type
        if self.new_type is not None and self.type is not None:
            return self.new_type != self.type
        if self.new_type is not None and self.new_mime_type is not None:
            return True
        return False
