import re
import asyncio

from typing import TYPE_CHECKING, Sequence

from tortoise import fields, models
from tortoise_serializer import ModelSerializer

from app.lib.helpers import clean_text

from app.models.common.base import TimestampMixin


if TYPE_CHECKING:
    from app.models.uploads import Upload, UploadSerializer  # noqa: F401
    from app.models.users import User, UserSerializer  # noqa: F401


class Collection(models.Model, TimestampMixin):
    id = fields.IntField(primary_key=True)
    user = fields.ForeignKeyField("models.User", related_name="collections", on_delete=fields.CASCADE)
    name = fields.CharField(max_length=255)
    name_unique = fields.CharField(max_length=255)

    class Meta:  # type: ignore[override]
        table = "collections"

    @classmethod
    async def _make_name_unique(cls, base_slug: str) -> str:
        """Return a globally unique name_unique slug derived from base_slug.

        If base_slug is not taken it is returned as-is.  If it is taken, a
        numeric suffix is appended (-2, -3, …) until a free slot is found.
        """
        candidates = [
            row["name_unique"]
            for row in await cls.filter(name_unique__startswith=base_slug).values("name_unique")
        ]

        # Only consider exact base or base-N variants to avoid false matches
        # (e.g. "my-trip" must not interfere with "my-trip-photos").
        pattern = re.compile(rf"^{re.escape(base_slug)}(-\d+)?$")
        matches = {n for n in candidates if pattern.match(n)}

        if not matches:
            return base_slug

        # Find the highest existing numeric suffix.
        max_n = 1  # the un-suffixed base counts as slot 1
        for m in matches:
            if m != base_slug:
                max_n = max(max_n, int(m[len(base_slug) + 1:]))

        return f"{base_slug}-{max_n + 1}"


    @classmethod
    async def get_or_create_for_user(cls, collection_name: str, user: "User | UserSerializer | int",) -> "Collection":
        """Create a collection for a user if it doesn't already exist"""

        # Get user_id
        if isinstance(user, int):
            user_id = user
        else:
            user_id = user.id  # type: ignore

        # Clean collection_name name
        if not collection_name or not collection_name.strip():
            raise ValueError("Collection name cannot be empty.")

        display_name = collection_name.strip()
        base_slug = clean_text(display_name)
        if not base_slug:
            raise ValueError("Collection name cannot be empty or contain only invalid characters.")

        # Locate the user's existing collection by display name, or create one.
        collection = await Collection.get_or_none(user_id=user_id, name=display_name)
        if collection is None:
            name_unique = await cls._make_name_unique(base_slug)
            collection = await Collection.create(
                name=display_name,
                name_unique=name_unique,
                user_id=user_id,
            )

        return collection


    @classmethod
    async def add_or_create_for_upload(cls, upload: "Upload", collection_name: str, user_id: int) -> "Collection":
        """Add an upload to a collection, creating the collection if it doesn't exist.

        Looks up an existing collection for this user by display name.  If none
        exists, a new collection is created with a globally unique name_unique slug.
        """

        collection = await Collection.get_or_create_for_user(collection_name=collection_name, user=user_id)

        # Link the upload to the collection.
        await upload.collections.add(collection)

        return collection


    @classmethod
    async def add_or_create_for_uploads(cls, uploads: list["Upload"], collection_name: str, user_id: int) -> "Collection":
        """Add multiple uploads to a collection, creating the collection if it doesn't exist.

        Looks up an existing collection for this user by display name.  If none
        exists, a new collection is created with a globally unique name_unique slug.
        """
        collection = await Collection.get_or_create_for_user(collection_name=collection_name, user=user_id)

        # Link the uploads to the collection.
        await asyncio.gather(*[upload.collections.add(collection) for upload in uploads])

        return collection


    @classmethod
    async def add_for_upload(cls, upload: "Upload", collection_id: int) -> bool:
        """Add an upload to an existing collection by ID. Returns False if the collection does not exist."""
        collection = await Collection.get_or_none(id=collection_id)
        if not collection:
            return False

        await upload.collections.add(collection)  # type: ignore[union-attr]
        return True

    @classmethod
    async def remove_from_upload(cls, upload: "Upload", collection_id: int) -> bool:
        """Remove an upload from a collection. Returns False if the collection does not exist."""
        collection = await Collection.get_or_none(id=collection_id)
        if not collection:
            return False

        await upload.collections.remove(collection)  # type: ignore[union-attr]
        return True

    @classmethod
    async def get_filtered_for_upload(cls, upload: "Upload", user: "User", name_filter: str = "", limit: int = 5) -> Sequence["Collection"]:
        """Return collections owned by user that are not already linked to upload.

        Results are ordered by name and capped at limit (default 5).  Pass
        name_filter to restrict results to collections whose name contains that
        string.
        """
        existing_ids = await upload.collections.filter(user=user).values_list("id", flat=True)  # type: ignore[union-attr]
        qs = cls.filter(user=user).exclude(id__in=existing_ids).limit(limit).order_by("name")
        if name_filter:
            qs = qs.filter(name__icontains=name_filter)
        return await qs

    @classmethod
    async def get_combined_ids_for_uploads(cls, user: "User", uploads: list["Upload"] | list["UploadSerializer"]) -> set[int]:
        """Build combined list of collection IDs from a provided list of Uploads"""

        if not uploads:
            return set()

        # Get all available collection IDs
        await user.fetch_related("collections")
        available_collection_ids = set(c.id for c in user.collections) # type: ignore
        assigned_collection_ids = {c.id for u in uploads for c in u.collections}
        combined_collection_ids = available_collection_ids & assigned_collection_ids

        return combined_collection_ids

    @classmethod
    async def get_combined_for_uploads(cls, user: "User", uploads: list["Upload"] | list["UploadSerializer"]) -> list[dict[str, str]]:
        """Build combined list of collections from a provided list of Uploads"""

        if not uploads:
            return []
        
        # Get all available collection IDs
        await user.fetch_related("collections")
        available_collection_ids = set(c.id for c in user.collections) # type: ignore
        assigned_collection_ids = {c.id for u in uploads for c in u.collections}
        combined_collection_ids = available_collection_ids & assigned_collection_ids

        # Determine common set of collection_ids across all provided uploads
        common_collection_ids = None
        for upload in uploads:
            upload_collection_ids = set(c.id for c in upload.collections)
            if common_collection_ids is None:
                common_collection_ids = upload_collection_ids
            elif common_collection_ids:
                if not upload_collection_ids:
                    common_collection_ids.clear()
                else:
                    common_collection_ids &= upload_collection_ids

        # Make a list of collections
        collections = []
        for collection_id in combined_collection_ids:
            collection_model = [c for c in user.collections if c.id == collection_id][0] # type: ignore
            collection_dict = CollectionSerializer.model_validate(collection_model, from_attributes=True).model_dump()

            if collection_model.id in common_collection_ids:
                collection_dict.update(selection_type="common")
            else:
                collection_dict.update(selection_type="partial")

            collections.append(collection_dict)

        return sorted(collections, key=lambda c: c["name"])


class CollectionUpload(models.Model):
    collection_id = fields.IntField()
    upload_id = fields.IntField()

    class Meta:  # type: ignore[override]
        table = "collection_upload"


class CollectionSerializer(ModelSerializer[Collection]):
    """Serializer for the Collection model."""

    # Model fields
    id: int
    user_id: int
    name: str
    name_unique: str
