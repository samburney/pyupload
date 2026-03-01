from typing import TYPE_CHECKING

from tortoise import fields, models
from tortoise_serializer import ModelSerializer

from app.lib.helpers import make_clean_tag

from app.models.common.base import TimestampMixin


if TYPE_CHECKING:
    from app.models.uploads import Upload  # noqa: F401


class Tag(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    name = fields.CharField(max_length=255)

    class Meta:  # type: ignore[override]
        table = "tags"

    @classmethod
    async def add_or_create_for_upload(cls, upload: "Upload", tag_name: str) -> "Tag":
        """Add a tag to an upload, creating the tag if it doesn't exist."""

        # Sanitise tag name
        tag_name = make_clean_tag(tag_name)
        if not tag_name:
            raise ValueError("Tag name cannot be empty or contain only invalid characters.")
        
        # Add tag to the upload, creating the tag if it doesn't exist
        tag, _ = await Tag.get_or_create(name=tag_name)
        await upload.tags.add(tag)

        return tag

    @classmethod
    async def remove_tag_from_upload(cls, upload: "Upload", tag_name: str) -> bool:
        """Add a tag to an upload, creating the tag if it doesn't exist."""

        # Sanitise tag name
        tag_name = make_clean_tag(tag_name)
        if not tag_name:
            raise ValueError("Tag name cannot be empty or contain only invalid characters.")
        
        # Get Tag object, return False if it doesn't exist
        tag = await Tag.get_or_none(name=tag_name)
        if not tag:
            return False
        
        # Remove from Upload
        await upload.tags.remove(tag)

        # Count the number of uploads with this tag
        count = await tag.uploads.all().count() # type: ignore[no-member]
        if count == 0:
            await tag.delete()

        return True


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
