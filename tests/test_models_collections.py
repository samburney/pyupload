"""Tests for app/models/collections.py — Collection model methods.

Validates:
- Collection._make_name_unique: slug uniqueness and de-collision logic
- Collection.get_or_create_for_user: creates/reuses collection by name for a given user
- Collection.add_or_create_for_upload: creates/reuses collections, validates input, links upload
- Collection.add_or_create_for_uploads: creates/reuses collections, validates input, links multiple uploads
- Collection.add_for_upload: links an existing collection, returns False for unknown ID
- Collection.remove_from_upload: removes a collection link, returns False for unknown ID
- Collection.get_filtered_for_upload: returns unlinked collections, supports name filtering
- Collection.get_combined_ids_for_uploads: returns IDs of user-owned collections on the given uploads
- Collection.get_combined_for_uploads: returns collection dicts with common/partial selection_type
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

    async def test_returns_base_slug_when_not_taken(self, db):
        """Returns the base slug unchanged when no collection uses it."""
        result = await Collection._make_name_unique("my-trip")

        assert result == "my-trip"

    async def test_appends_2_when_base_slug_exists(self, db):
        """Appends -2 when the base slug is already taken."""
        user, _ = await _make_user_upload("nu1")
        await Collection.create(user=user, name="My Trip", name_unique="my-trip")

        result = await Collection._make_name_unique("my-trip")

        assert result == "my-trip-2"

    async def test_increments_past_2_when_multiple_exist(self, db):
        """Appends -3 when both base and -2 are taken."""
        user, _ = await _make_user_upload("nu2")
        await Collection.create(user=user, name="My Trip", name_unique="my-trip")
        await Collection.create(user=user, name="My Trip 2", name_unique="my-trip-2")

        result = await Collection._make_name_unique("my-trip")

        assert result == "my-trip-3"

    async def test_similar_slug_does_not_cause_false_conflict(self, db):
        """'my-trip-photos' must not prevent 'my-trip' from being returned as-is."""
        user, _ = await _make_user_upload("nu3")
        await Collection.create(user=user, name="My Trip Photos", name_unique="my-trip-photos")

        result = await Collection._make_name_unique("my-trip")

        assert result == "my-trip"


class TestAddOrCreateForUpload:
    """Tests for Collection.add_or_create_for_upload."""

    async def test_creates_new_collection_and_links_upload(self, db):
        """Creates a new Collection and links the upload to it."""
        user, upload = await _make_user_upload("ac1")

        collection = await Collection.add_or_create_for_upload(upload, "Holiday Snaps", user_id=user.id)

        assert collection.id is not None
        assert collection.name == "Holiday Snaps"
        await upload.fetch_related("collections")
        assert any(c.id == collection.id for c in upload.collections)

    async def test_reuses_existing_collection_by_name(self, db):
        """Returns the existing collection when user already has one with the same name."""
        user, upload = await _make_user_upload("ac2")
        existing = await Collection.create(user=user, name="Holidays", name_unique="holidays")

        collection = await Collection.add_or_create_for_upload(upload, "Holidays", user_id=user.id)

        assert collection.id == existing.id
        assert await Collection.filter(user=user).count() == 1

    async def test_generates_globally_unique_slug(self, db):
        """Ensures name_unique is globally unique even across different users."""
        user1, upload1 = await _make_user_upload("ac3a")
        user2, upload2 = await _make_user_upload("ac3b")
        await Collection.create(user=user1, name="Holiday", name_unique="holiday")

        col = await Collection.add_or_create_for_upload(upload2, "Holiday", user_id=user2.id)

        assert col.name_unique == "holiday-2"

    async def test_strips_whitespace_from_display_name(self, db):
        """Leading/trailing whitespace is stripped from the collection name."""
        user, upload = await _make_user_upload("ac4")

        collection = await Collection.add_or_create_for_upload(upload, "  Summer  ", user_id=user.id)

        assert collection.name == "Summer"

    async def test_raises_for_empty_name(self, db):
        """Raises ValueError when the name is empty."""
        user, upload = await _make_user_upload("ac5")

        with pytest.raises(ValueError):
            await Collection.add_or_create_for_upload(upload, "", user_id=user.id)

    async def test_raises_for_whitespace_only_name(self, db):
        """Raises ValueError when the name contains only whitespace."""
        user, upload = await _make_user_upload("ac6")

        with pytest.raises(ValueError):
            await Collection.add_or_create_for_upload(upload, "   ", user_id=user.id)

    async def test_raises_when_slug_reduces_to_empty(self, db):
        """Raises ValueError when clean_text produces an empty slug from the name."""
        user, upload = await _make_user_upload("ac7")

        with pytest.raises(ValueError):
            await Collection.add_or_create_for_upload(upload, "!@#$%", user_id=user.id)


class TestAddForUpload:
    """Tests for Collection.add_for_upload."""

    async def test_links_existing_collection_to_upload(self, db):
        """Returns True and adds the collection to the upload."""
        user, upload = await _make_user_upload("af1")
        collection = await Collection.create(user=user, name="Existing", name_unique="existing")

        result = await Collection.add_for_upload(upload, collection.id)

        assert result is True
        await upload.fetch_related("collections")
        assert any(c.id == collection.id for c in upload.collections)

    async def test_returns_false_for_nonexistent_collection(self, db):
        """Returns False when no collection with the given ID exists."""
        _, upload = await _make_user_upload("af2")

        result = await Collection.add_for_upload(upload, 999999)

        assert result is False


class TestRemoveFromUpload:
    """Tests for Collection.remove_from_upload."""

    async def test_removes_collection_from_upload(self, db):
        """Returns True and removes the collection from the upload."""
        user, upload = await _make_user_upload("rf1")
        collection = await Collection.create(user=user, name="To Remove", name_unique="to-remove")
        await upload.collections.add(collection)

        result = await Collection.remove_from_upload(upload, collection.id)

        assert result is True
        await upload.fetch_related("collections")
        assert all(c.id != collection.id for c in upload.collections)

    async def test_returns_false_for_nonexistent_collection(self, db):
        """Returns False when no collection with the given ID exists."""
        _, upload = await _make_user_upload("rf2")

        result = await Collection.remove_from_upload(upload, 999999)

        assert result is False


class TestGetFilteredForUpload:
    """Tests for Collection.get_filtered_for_upload."""

    async def test_returns_unlinked_collections(self, db):
        """Returns collections not yet linked to the upload."""
        user, upload = await _make_user_upload("gf1")
        linked = await Collection.create(user=user, name="Linked", name_unique="linked-gf1")
        unlinked = await Collection.create(user=user, name="Unlinked", name_unique="unlinked-gf1")
        await upload.collections.add(linked)

        result = await Collection.get_filtered_for_upload(upload, user)

        result_ids = [c.id for c in result]
        assert unlinked.id in result_ids
        assert linked.id not in result_ids

    async def test_excludes_other_users_collections(self, db):
        """Does not return collections belonging to a different user."""
        user, upload = await _make_user_upload("gf2a")
        other_user, _ = await _make_user_upload("gf2b")
        await Collection.create(user=other_user, name="Other", name_unique="other-gf2")
        own = await Collection.create(user=user, name="Own", name_unique="own-gf2")

        result = await Collection.get_filtered_for_upload(upload, user)

        result_ids = [c.id for c in result]
        assert own.id in result_ids
        assert all(c.user_id == user.id for c in result)

    async def test_name_filter_restricts_results(self, db):
        """name_filter limits results to collections whose name contains the string."""
        user, upload = await _make_user_upload("gf3")
        await Collection.create(user=user, name="Holiday Photos", name_unique="holiday-photos-gf3")
        await Collection.create(user=user, name="Work Stuff", name_unique="work-stuff-gf3")

        result = await Collection.get_filtered_for_upload(upload, user, name_filter="holiday")

        assert len(result) == 1
        assert result[0].name == "Holiday Photos"

    async def test_empty_name_filter_returns_all(self, db):
        """An empty name_filter returns all unlinked collections (up to 5)."""
        user, upload = await _make_user_upload("gf4")
        await Collection.create(user=user, name="Alpha", name_unique="alpha-gf4")
        await Collection.create(user=user, name="Beta", name_unique="beta-gf4")

        result = await Collection.get_filtered_for_upload(upload, user, name_filter="")

        assert len(result) == 2

    async def test_results_limited_to_five_by_default(self, db):
        """Returns at most 5 collections by default when more exist."""
        user, upload = await _make_user_upload("gf5")
        for i in range(8):
            await Collection.create(user=user, name=f"Col {i}", name_unique=f"col-{i}-gf5")

        result = await Collection.get_filtered_for_upload(upload, user)

        assert len(result) == 5

    async def test_custom_limit_is_respected(self, db):
        """A custom limit parameter overrides the default of 5."""
        user, upload = await _make_user_upload("gf6")
        for i in range(4):
            await Collection.create(user=user, name=f"Col {i}", name_unique=f"col-{i}-gf6")

        result = await Collection.get_filtered_for_upload(upload, user, limit=2)

        assert len(result) == 2


class TestGetOrCreateForUser:
    """Tests for Collection.get_or_create_for_user."""

    async def test_creates_new_collection_for_user(self, db):
        """Creates a new Collection when none with that name exists for the user."""
        user, _ = await _make_user_upload("goc1")

        collection = await Collection.get_or_create_for_user("New Collection", user=user.id)

        assert collection.id is not None
        assert collection.name == "New Collection"
        assert collection.user_id == user.id

    async def test_reuses_existing_collection_by_name(self, db):
        """Returns the existing collection when one with the same name already exists."""
        user, _ = await _make_user_upload("goc2")
        existing = await Collection.create(user=user, name="Existing", name_unique="existing-goc2")

        collection = await Collection.get_or_create_for_user("Existing", user=user.id)

        assert collection.id == existing.id
        assert await Collection.filter(user=user).count() == 1

    async def test_accepts_integer_user_id(self, db):
        """Accepts a plain int for the user parameter."""
        user, _ = await _make_user_upload("goc3")

        collection = await Collection.get_or_create_for_user("Int User", user=user.id)

        assert collection.user_id == user.id

    async def test_raises_for_empty_name(self, db):
        """Raises ValueError when the collection name is empty."""
        user, _ = await _make_user_upload("goc4")

        with pytest.raises(ValueError):
            await Collection.get_or_create_for_user("", user=user.id)

    async def test_raises_when_slug_reduces_to_empty(self, db):
        """Raises ValueError when clean_text produces an empty slug."""
        user, _ = await _make_user_upload("goc5")

        with pytest.raises(ValueError):
            await Collection.get_or_create_for_user("!@#$%", user=user.id)

    async def test_strips_whitespace_from_name(self, db):
        """Leading/trailing whitespace is stripped from the display name."""
        user, _ = await _make_user_upload("goc6")

        collection = await Collection.get_or_create_for_user("  Trimmed  ", user=user.id)

        assert collection.name == "Trimmed"


class TestAddOrCreateForUploads:
    """Tests for Collection.add_or_create_for_uploads (plural)."""

    async def test_creates_collection_and_links_all_uploads(self, db):
        """Creates a new collection and links it to every upload in the list."""
        user, upload1 = await _make_user_upload("acu1a")
        _, upload2 = await _make_user_upload("acu1b")
        # Give upload2 the same user so ownership works
        upload2.user_id = user.id
        await upload2.save()

        collection = await Collection.add_or_create_for_uploads([upload1, upload2], "Shared", user_id=user.id)

        assert collection.name == "Shared"
        await upload1.fetch_related("collections")
        await upload2.fetch_related("collections")
        assert any(c.id == collection.id for c in upload1.collections)
        assert any(c.id == collection.id for c in upload2.collections)

    async def test_reuses_existing_collection(self, db):
        """Reuses an existing collection rather than creating a duplicate."""
        user, upload = await _make_user_upload("acu2")
        existing = await Collection.create(user=user, name="Reused", name_unique="reused-acu2")

        collection = await Collection.add_or_create_for_uploads([upload], "Reused", user_id=user.id)

        assert collection.id == existing.id
        assert await Collection.filter(user=user).count() == 1

    async def test_raises_for_empty_name(self, db):
        """Raises ValueError when the collection name is empty."""
        user, upload = await _make_user_upload("acu3")

        with pytest.raises(ValueError):
            await Collection.add_or_create_for_uploads([upload], "", user_id=user.id)


class TestGetCombinedIdsForUploads:
    """Tests for Collection.get_combined_ids_for_uploads."""

    async def test_returns_empty_set_for_empty_uploads(self, db):
        """Returns an empty set when no uploads are provided."""
        user, _ = await _make_user_upload("gcids1")

        result = await Collection.get_combined_ids_for_uploads(user, [])

        assert result == set()

    async def test_returns_ids_of_user_owned_assigned_collections(self, db):
        """Returns IDs that are both owned by the user and assigned to an upload."""
        user, upload = await _make_user_upload("gcids2")
        col = await Collection.create(user=user, name="Mine", name_unique="mine-gcids2")
        await upload.collections.add(col)
        await upload.fetch_related("collections")

        result = await Collection.get_combined_ids_for_uploads(user, [upload])

        assert col.id in result

    async def test_excludes_other_users_collections(self, db):
        """Does not include collections owned by a different user."""
        user, upload = await _make_user_upload("gcids3a")
        other, _ = await _make_user_upload("gcids3b")
        other_col = await Collection.create(user=other, name="Not Mine", name_unique="not-mine-gcids3")
        await upload.collections.add(other_col)
        await upload.fetch_related("collections")

        result = await Collection.get_combined_ids_for_uploads(user, [upload])

        assert other_col.id not in result

    async def test_excludes_unassigned_user_collections(self, db):
        """Does not include user-owned collections that are not on any of the uploads."""
        user, upload = await _make_user_upload("gcids4")
        await Collection.create(user=user, name="Unassigned", name_unique="unassigned-gcids4")
        await upload.fetch_related("collections")

        result = await Collection.get_combined_ids_for_uploads(user, [upload])

        assert result == set()


class TestGetCombinedForUploads:
    """Tests for Collection.get_combined_for_uploads."""

    async def test_returns_empty_list_for_empty_uploads(self, db):
        """Returns an empty list when no uploads are provided."""
        user, _ = await _make_user_upload("gcf1")

        result = await Collection.get_combined_for_uploads(user, [])

        assert result == []

    async def test_single_upload_collection_is_common(self, db):
        """A collection on a single upload is marked as 'common'."""
        user, upload = await _make_user_upload("gcf2")
        col = await Collection.create(user=user, name="Solo", name_unique="solo-gcf2")
        await upload.collections.add(col)
        await upload.fetch_related("collections")

        result = await Collection.get_combined_for_uploads(user, [upload])

        assert len(result) == 1
        assert result[0].id == col.id
        assert result[0].selection_type == "common"

    async def test_collection_on_all_uploads_is_common(self, db):
        """A collection present on every upload is marked as 'common'."""
        user, upload1 = await _make_user_upload("gcf3a")
        upload2 = await Upload.create(**_upload_kwargs(user, "gcf3b"))
        col = await Collection.create(user=user, name="Common", name_unique="common-gcf3")
        await upload1.collections.add(col)
        await upload2.collections.add(col)
        await upload1.fetch_related("collections")
        await upload2.fetch_related("collections")

        result = await Collection.get_combined_for_uploads(user, [upload1, upload2])

        assert len(result) == 1
        assert result[0].selection_type == "common"

    async def test_collection_on_subset_of_uploads_is_partial(self, db):
        """A collection present on only some uploads is marked as 'partial'."""
        user, upload1 = await _make_user_upload("gcf4a")
        upload2 = await Upload.create(**_upload_kwargs(user, "gcf4b"))
        col = await Collection.create(user=user, name="Partial", name_unique="partial-gcf4")
        await upload1.collections.add(col)
        # upload2 does NOT have the collection
        await upload1.fetch_related("collections")
        await upload2.fetch_related("collections")

        result = await Collection.get_combined_for_uploads(user, [upload1, upload2])

        assert len(result) == 1
        assert result[0].selection_type == "partial"

    async def test_excludes_other_users_collections(self, db):
        """Collections not owned by current_user are excluded even if on the upload."""
        user, upload = await _make_user_upload("gcf5a")
        other, _ = await _make_user_upload("gcf5b")
        other_col = await Collection.create(user=other, name="Not Mine", name_unique="not-mine-gcf5")
        await upload.collections.add(other_col)
        await upload.fetch_related("collections")

        result = await Collection.get_combined_for_uploads(user, [upload])

        assert result == []

    async def test_result_dicts_contain_expected_keys(self, db):
        """Each returned dict includes id, name, name_unique, user_id and selection_type."""
        user, upload = await _make_user_upload("gcf6")
        col = await Collection.create(user=user, name="Keys Test", name_unique="keys-test-gcf6")
        await upload.collections.add(col)
        await upload.fetch_related("collections")

        result = await Collection.get_combined_for_uploads(user, [upload])

        assert len(result) == 1
        entry = result[0]
        assert entry.id is not None
        assert entry.name is not None
        assert entry.name_unique is not None
        assert entry.user_id is not None
        assert entry.selection_type is not None
