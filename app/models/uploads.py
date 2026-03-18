import asyncio

from typing import Annotated, Optional, TYPE_CHECKING
from pydantic import BaseModel, StringConstraints
from pathlib import Path
from tortoise import fields, models
from tortoise.exceptions import NoValuesFetched
from tortoise_serializer import ModelSerializer, ContextType

from app.lib.config import get_app_config
from app.lib.helpers import MIME_TYPE_PATTERN, IMAGE_CONVERSION_DST_FORMATS, split_filename
from app.lib.file_io import delete_file
from app.lib.image_processing import do_image_rotation

from app.models.common.base import TimestampMixin, SerializerTimestampMixin
from app.models.common.pagination import PaginationMixin
from app.models.collections import Collection, CollectionSerializer
from app.models.users import User, UserSerializer
from app.models.images import ImageSerializer, ImageMetadata
from app.models.tags import TagSerializer


if TYPE_CHECKING:
    from app.models.images import Image
    from tortoise.queryset import QuerySet, QuerySetSingle


config = get_app_config()


# Validation patterns
EXTENSION_PATTERN = r'^[a-zA-Z0-9.-]{1,10}$'
CLEAN_FILENAME_PATTERN = r'[a-z0-9](?:[a-z0-9_]*[a-z0-9])?'
DATETIME_STAMP_PATTERN = r'\d{8}-\d{6}'
SHORT_UUID_PATTERN = r'[a-f0-9]{8}'
UNIQUE_FILENAME_PATTERN = rf'^{CLEAN_FILENAME_PATTERN}_{DATETIME_STAMP_PATTERN}_{SHORT_UUID_PATTERN}$'

# Related fields that are commonly prefetched together for UploadSerializer
UPLOAD_PREFETCH_MODELS = ("user", "images", "tags", "collections")


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
    tags = fields.ManyToManyField(
        "models.Tag", related_name="uploads", through="tag_upload", forward_key="upload_id", backward_key="tag_id"
    )
    collections = fields.ManyToManyField(
        "models.Collection", related_name="uploads", through="collection_upload", forward_key="upload_id", backward_key="collection_id"
    )
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
        indexes = (
            ("private", "created_at"),
        )

    class PydanticMeta:
        # Exclude fields that should not be included in the Pydantic model
        # - extra: Deprecated value which will be removed from the database model in a future revision
        # - user: A FK relationship which causes verbose output.  We already know the user (or can fetch it based on `user_id`)
        # - images.*: We don't need to include these values, we already know them as they are part of the `Upload` model
        exclude = (
            "extra",
            "user",
            "images.created_at",
            "images.updated_at",
            "images.id",
            "images.upload_id",
        )

    @property
    def display_name(self) -> str:
        """Return a user-friendly display name for the upload."""
        return self.description if self.description else self.originalname

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

    @property
    def short_type(self) -> str:
        """Return the short type of the file."""

        type_split = self.type.split("/")

        if type_split[0] in ("image", "video", "audio"):
            return type_split[1]

        if self.ext != "":
            return self.ext

        return type_split[0]

    @property
    async def image_metadata(self) -> Optional[ImageMetadata]:
        """Return the image metadata for this upload, if it exists."""
        if self.is_image:
            image = await self.images.all().first()

            if image:
                return ImageMetadata(
                    upload_id=self.id,
                    type=getattr(image, "type"),
                    width=getattr(image, "width"),
                    height=getattr(image, "height"),
                    bits=getattr(image, "bits"),
                    channels=getattr(image, "channels"),
                )

        return None

    async def delete(self):
        """Delete the file from disk and its related database record."""
        await super().delete()
        await asyncio.to_thread(delete_file, self.filepath)

    def is_owner(self, user: User) -> bool:
        """Return whether or not this file is owned by the current user."""
        return getattr(self, "user_id") == user.id
    
    def user_collections(self, user: User) -> "QuerySet[Collection]":
        """Return a queryset of collections that the current user has which include this upload."""
        return self.collections.filter(user=user)  # type: ignore[return-value]
    
    async def rotate_image(self, angle: int) -> bool:
        """Rotate the image by a specified angle. Returns True if successful."""
        if not self.is_image:
            raise ValueError("Cannot rotate a non-image file.")
        
        # Call the image processing function to handle rotation
        new_image_metadata: ImageMetadata = await do_image_rotation(self, angle)

        # Update the related Image record with the new metadata
        image = await self.images.all().first()
        if image is None:
            raise ValueError("No related image record found for this upload.")
        
        image.width = new_image_metadata.width
        image.height = new_image_metadata.height
        await image.save()

        # Update upload metadata to reflect the new image properties
        self.size = self.filepath.stat().st_size
        await self.save()

        return True

    async def fetch_relations(self) -> None:
        """Fetch related fields for this upload instance."""
        await self.fetch_related(*UPLOAD_PREFETCH_MODELS)

    @classmethod
    def get_with_relations(cls, id: int) -> "QuerySetSingle[Upload | None]":
        """Return a get_or_none queryset with all relations required by UploadSerializer prefetched."""
        return cls.get_or_none(id=id).prefetch_related(*UPLOAD_PREFETCH_MODELS)


class UploadSerializer(ModelSerializer[Upload], SerializerTimestampMixin):
    """Serializer for the Upload model."""

    # Model fields
    id: int
    user: UserSerializer
    tags: list[TagSerializer]
    collections: list[CollectionSerializer]
    description: str
    name: str
    cleanname: str
    originalname: str
    ext: str
    size: int
    type: str
    extra: str
    viewed: int
    private: int
    image: ImageSerializer | None = None
    user_collections: Optional[list[CollectionSerializer]] = None
    filtered_collections: Optional[list[CollectionSerializer]] = None

    @classmethod
    async def resolve_image(cls, instance: Upload, context: ContextType) -> ImageSerializer | None:
        """Resolve the image for the upload."""
        if instance.images:
            # Get related image records
            images_queryset = instance.images.all()
            images = await ImageSerializer.from_queryset(images_queryset)
            if len(images) == 1:
                return images[0]

        return None
    
    @classmethod
    async def resolve_user_collections(cls, instance: Upload, context: ContextType) -> Optional[list[CollectionSerializer]]:
        """Resolve the user's collections that include this upload."""
        user = context.get("user")
        if user is None:
            return None

        user_collections = await CollectionSerializer.from_queryset(instance.user_collections(user))
        if user_collections:
            return user_collections
        return []
    
    @classmethod
    async def resolve_filtered_collections(cls, instance: Upload, context: ContextType) -> Optional[list[CollectionSerializer]]:
        """Return collections owned by user that are not already linked to upload."""
        user = context.get("user")
        if user is None:
            return None

        filtered_collections = await Collection.get_filtered_for_upload(instance, user)

        return await asyncio.gather(*[CollectionSerializer.from_tortoise_orm(c) for c in filtered_collections])

    # Computed fields
    display_name: str
    dot_ext: str
    filepath: Path
    filename: str
    url: str
    view_url: str
    download_url: str
    is_image: bool
    is_private: bool
    short_type: str

    def autoresize_url(self, max_width: int) -> str:
        """Return a resized image URL constrained to max_width, preserving format where possible.

        If the image doesn't support processing or is already smaller than max_width,
        returns the original URL unchanged.
        """
        if not self.image or not self.image.supports_processing:
            return self.url

        if self.image.width <= max_width:
            return self.url

        # Determine output extension: preserve original if it's a supported output format, else .jpg
        image_ext = f".{self.image.type}"
        if image_ext in IMAGE_CONVERSION_DST_FORMATS:
            out_ext = image_ext
        else:
            out_ext = ".jpg"

        base, _ = split_filename(self.url)
        return f"{base}-{max_width}x0{out_ext}"


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
