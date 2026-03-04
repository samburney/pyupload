"""Tests for app/models/collections.py — Collection model methods.

Validates:
- Collection._make_name_unique: slug uniqueness and de-collision logic
- Collection.add_or_create_for_upload: creates/reuses collections, validates input, links uploads
- Collection.add_for_upload: links an existing collection, returns False for unknown ID
- Collection.remove_from_upload: removes a collection link, returns False for unknown ID
"""
import pytest

from app.models.users import User
from app.models.uploads import Upload
from app.models.collections import Collection


def _upload_kwargs(user, suffix: str = "") -> dict:
    """Return minimal Upload.create kwargs."""
    return {
        "user": user,
        "description": f"test{suffix}",
        "name": f"file{suffix}_20250101-000000_a1b2c3d4",
        "cleanname": f"file{suffix}",
        "originalname": f"file{suffix}.txt",
        "ext": "txt",
        "size": 10,
        "type": "text/plain",
        "extra": "0",
    }


async def _make_user_upload(suffix: str = "") -> tuple[User, Upload]:
    user = await User.create(
        username=f"coltest{suffix}",
        email=f"coltest{suffix}@example.com",
        password="pw",
    )
    upload = await Upload.create(**_upload_kwargs(user, suffix))
    return user, upload


class TestMakeNameUnique:
    """Tests for Collection._make_name_unique."""

    @pytest.mark.asyncio
    async def test_returns_base_slug_when_not_taken(self, db):
        """Returns the base slug unchanged when no collection uses it."""
        result = await Collection._make_name_unique("my-trip")

        assert result == "my-trip"

    @pytest.mark.asyncio
    async def test_appends_2_when_base_slug_exists(self, db):
        """Appends -2 when the base slug is already taken."""
        user, _ = await _make_user_upload("nu1")
        await Collection.create(user=user, name="My Trip", name_unique="my-trip")

        result = await Collection._make_name_unique("my-trip")

        assert result == "my-trip-2"

    @pytest.mark.asyncio
    async def test_increments_past_2_when_multiple_exist(self, db):
        """Appends -3 when both base and -2 are taken."""
        user, _ = await _make_user_upload("nu2")
        await Collection.create(user=user, name="My Trip", name_unique="my-trip")
        await Collection.create(user=user, name="My Trip 2", name_unique="my-trip-2")

        result = await Collection._make_name_unique("my-trip")

        assert result == "my-trip-3"

    @pytest.mark.asyncio
    async def test_similar_slug_does_not_cause_false_conflict(self, db):
        """'my-trip-photos' must not prevent 'my-trip' from being returned as-is."""
        user, _ = await _make_user_upload("nu3")
        await Collection.create(user=user, name="My Trip Photos", name_unique="my-trip-photos")

        result = await Collection._make_name_unique("my-trip")

        assert result == "my-trip"


class TestAddOrCreateForUpload:
    """Tests for Collection.add_or_create_for_upload."""

    @pytest.mark.asyncio
    async def test_creates_new_collection_and_links_upload(self, db):
        """Creates a new Collection and links the upload to it."""
        user, upload = await _make_user_upload("ac1")

        collection = await Collection.add_or_create_for_upload(upload, "Holiday Snaps", user_id=user.id)

        assert collection.id is not None
        assert collection.name == "Holiday Snaps"
        await upload.fetch_related("collections")
        assert any(c.id == collection.id for c in upload.collections)

    @pytest.mark.asyncio
    async def test_reuses_existing_collection_by_name(self, db):
        """Returns the existing collection when user already has one with the same name."""
        user, upload = await _make_user_upload("ac2")
        existing = await Collection.create(user=user, name="Holidays", name_unique="holidays")

        collection = await Collection.add_or_create_for_upload(upload, "Holidays", user_id=user.id)

        assert collection.id == existing.id
        assert await Collection.filter(user=user).count() == 1

    @pytest.mark.asyncio
    async def test_generates_globally_unique_slug(self, db):
        """Ensures name_unique is globally unique even across different users."""
        user1, upload1 = await _make_user_upload("ac3a")
        user2, upload2 = await _make_user_upload("ac3b")
        await Collection.create(user=user1, name="Holiday", name_unique="holiday")

        col = await Collection.add_or_create_for_upload(upload2, "Holiday", user_id=user2.id)

        assert col.name_unique == "holiday-2"

    @pytest.mark.asyncio
    async def test_strips_whitespace_from_display_name(self, db):
        """Leading/trailing whitespace is stripped from the collection name."""
        user, upload = await _make_user_upload("ac4")

        collection = await Collection.add_or_create_for_upload(upload, "  Summer  ", user_id=user.id)

        assert collection.name == "Summer"

    @pytest.mark.asyncio
    async def test_raises_for_empty_name(self, db):
        """Raises ValueError when the name is empty."""
        user, upload = await _make_user_upload("ac5")

        with pytest.raises(ValueError):
            await Collection.add_or_create_for_upload(upload, "", user_id=user.id)

    @pytest.mark.asyncio
    async def test_raises_for_whitespace_only_name(self, db):
        """Raises ValueError when the name contains only whitespace."""
        user, upload = await _make_user_upload("ac6")

        with pytest.raises(ValueError):
            await Collection.add_or_create_for_upload(upload, "   ", user_id=user.id)

    @pytest.mark.asyncio
    async def test_raises_when_slug_reduces_to_empty(self, db):
        """Raises ValueError when clean_text produces an empty slug from the name."""
        user, upload = await _make_user_upload("ac7")

        with pytest.raises(ValueError):
            await Collection.add_or_create_for_upload(upload, "!@#$%", user_id=user.id)


class TestAddForUpload:
    """Tests for Collection.add_for_upload."""

    @pytest.mark.asyncio
    async def test_links_existing_collection_to_upload(self, db):
        """Returns True and adds the collection to the upload."""
        user, upload = await _make_user_upload("af1")
        collection = await Collection.create(user=user, name="Existing", name_unique="existing")

        result = await Collection.add_for_upload(upload, collection.id)

        assert result is True
        await upload.fetch_related("collections")
        assert any(c.id == collection.id for c in upload.collections)

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_collection(self, db):
        """Returns False when no collection with the given ID exists."""
        _, upload = await _make_user_upload("af2")

        result = await Collection.add_for_upload(upload, 999999)

        assert result is False


class TestRemoveFromUpload:
    """Tests for Collection.remove_from_upload."""

    @pytest.mark.asyncio
    async def test_removes_collection_from_upload(self, db):
        """Returns True and removes the collection from the upload."""
        user, upload = await _make_user_upload("rf1")
        collection = await Collection.create(user=user, name="To Remove", name_unique="to-remove")
        await upload.collections.add(collection)

        result = await Collection.remove_from_upload(upload, collection.id)

        assert result is True
        await upload.fetch_related("collections")
        assert all(c.id != collection.id for c in upload.collections)

    @pytest.mark.asyncio
    async def test_returns_false_for_nonexistent_collection(self, db):
        """Returns False when no collection with the given ID exists."""
        _, upload = await _make_user_upload("rf2")

        result = await Collection.remove_from_upload(upload, 999999)

        assert result is False
