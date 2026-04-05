from datetime import datetime
from typing import TYPE_CHECKING, Annotated, Literal

from tortoise import fields, models
from tortoise_serializer import ModelSerializer

from app.lib.helpers import make_clean_tag

from app.models.common.base import TimestampMixin, SerializerTimestampMixin


if TYPE_CHECKING:
    from app.models.uploads import Upload, UploadSerializer  # noqa: F401


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


    @classmethod
    def get_combined_for_uploads(cls, uploads: list["Upload"] | list["UploadSerializer"]) -> list["TagSerializerSelected"]:
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
            tags.append(TagSerializerSelected(
                name=tag_name,
                selection_type="common" if tag_name in common_tag_names else "partial",
            ))

        return sorted(tags, key=lambda t: t.name)


class TagUpload(models.Model):
    tag_id = fields.IntField()
    upload_id = fields.IntField()

    class Meta:  # type: ignore[override]
        table = "tag_upload"


class _TagSerializerBase(ModelSerializer[Tag]):
    """Base model for Serializer including mandatory fields"""

    name: str


class TagSerializer(_TagSerializerBase, SerializerTimestampMixin):
    """Serializer for the Tag model."""

    id: int


class TagSerializerSelected(_TagSerializerBase):
    """Model object for selected tag metadata, built from tag names without a full model lookup."""

    id: int | None = None
    created_at: datetime | None = None
    updated_at: datetime | None = None
    selection_type: Annotated[str, Literal['common', 'partial']]

    async def _populate_lazy_fields(self) -> Tag:
        """Fetch and cache lazy fields if requested"""

        tag_model = await Tag.get(name=self.name)
        self.id = tag_model.id
        self.created_at = tag_model.created_at
        self.updated_at = tag_model.updated_at

        return tag_model

    async def fetch_id(self) -> int:
        if self.id is None:
            await self._populate_lazy_fields()
        return self.id  # type: ignore[return-value]

    async def fetch_created_at(self) -> datetime:
        if self.created_at is None:
            await self._populate_lazy_fields()
        return self.created_at  # type: ignore[return-value]

    async def fetch_updated_at(self) -> datetime:
        if self.updated_at is None:
            await self._populate_lazy_fields()
        return self.updated_at  # type: ignore[return-value]
