from tortoise import fields, models
from tortoise_serializer import ModelSerializer

from app.models.common.base import TimestampMixin


class Tag(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)

    class Meta:  # type: ignore[override]
        table = "tags"


class TagUpload(models.Model):
    tag_id = fields.IntField()
    upload_id = fields.IntField()

    class Meta:  # type: ignore[override]
        table = "tag_upload"


class TagSerializer(ModelSerializer[Tag]):
    """Serializer for the Tag model."""

    # Model fields
    id: int
    name: str
