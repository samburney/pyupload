from typing import TYPE_CHECKING

from tortoise import fields, models
from tortoise_serializer import ModelSerializer

from app.lib.helpers import make_clean_tag

from app.models.common.base import TimestampMixin


if TYPE_CHECKING:
    from app.models.uploads import Upload, UploadSerializer  # noqa: F401


def get_combined_tags_for_uploads(uploads: list["Upload"] | list["UploadSerializer"]) -> list[dict[str, str]]:
    """Build combined list of tags from a provided list of Uploads"""

    if not uploads:
        return []

    combined_tag_names = set()
    common_tag_names = None

    for upload in uploads:
        tag_names = set(tag.name for tag in upload.tags)
        combined_tag_names.update(tag_names)
        if common_tag_names is None:
            common_tag_names = set(tag_names)
        elif common_tag_names:
            if not tag_names:
                common_tag_names.clear()
            else:
                common_tag_names &= tag_names

    # Make tags list of dicts
    tags = []
    for tag_name in combined_tag_names:
        tags.append({
            "name": tag_name,
            "selection_type": "common" if tag_name in common_tag_names else "partial",
        })

    return tags


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
        """Remove a tag from an upload, deleting the tag if it has no remaining uploads."""

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
