"""Tests for app/models/tags.py - Tag model methods.

Validates:
- Tag.add_or_create_for_upload: creates tags, reuses existing ones, sanitises names, raises on empty
- Tag.remove_tag_from_upload: removes association, deletes orphaned tags, preserves shared tags
"""
import pytest

from app.models.users import User
from app.models.uploads import Upload
from app.models.tags import Tag


def _make_upload_data(user, suffix: str = "") -> dict:
    """Return minimal Upload.create() kwargs for a given user."""
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


async def _make_user_and_upload(suffix: str = "") -> tuple[User, Upload]:
    user = await User.create(
        username=f"tagtest{suffix}",
        email=f"tagtest{suffix}@example.com",
        password="pw",
    )
    upload = await Upload.create(**_make_upload_data(user, suffix))
    return user, upload


class TestTagAddOrCreateForUpload:
    """Tests for Tag.add_or_create_for_upload class method."""

    async def test_creates_new_tag(self, db):
        """Creates a new Tag record when the name does not yet exist."""
        _, upload = await _make_user_and_upload("a1")

        tag = await Tag.add_or_create_for_upload(upload, "newtag")

        assert tag.id is not None
        assert tag.name == "newtag"
        assert await Tag.filter(name="newtag").count() == 1

    async def test_reuses_existing_tag(self, db):
        """Returns the existing Tag and does not create a duplicate."""
        _, upload = await _make_user_and_upload("a2")
        existing = await Tag.create(name="existing")

        tag = await Tag.add_or_create_for_upload(upload, "existing")

        assert tag.id == existing.id
        assert await Tag.filter(name="existing").count() == 1

    async def test_adds_tag_to_upload(self, db):
        """The upload gains the tag in its many-to-many relation."""
        _, upload = await _make_user_and_upload("a3")

        await Tag.add_or_create_for_upload(upload, "attached")

        await upload.fetch_related("tags")
        tag_names = [t.name for t in upload.tags]
        assert "attached" in tag_names

    async def test_sanitises_tag_name(self, db):
        """Input is cleaned via make_clean_tag before persisting."""
        _, upload = await _make_user_and_upload("a4")

        tag = await Tag.add_or_create_for_upload(upload, "Hello World!")

        assert tag.name == "hello-world"

    async def test_raises_for_empty_tag_name(self, db):
        """ValueError raised when the cleaned name is empty."""
        _, upload = await _make_user_and_upload("a5")

        with pytest.raises(ValueError):
            await Tag.add_or_create_for_upload(upload, "")

    async def test_raises_for_only_invalid_chars(self, db):
        """ValueError raised when the name contains only invalid characters."""
        _, upload = await _make_user_and_upload("a6")

        with pytest.raises(ValueError):
            await Tag.add_or_create_for_upload(upload, "!@#$%")

    async def test_adding_same_tag_twice_is_idempotent(self, db):
        """Adding the same tag twice does not create a duplicate association."""
        _, upload = await _make_user_and_upload("a7")

        await Tag.add_or_create_for_upload(upload, "idempotent")
        await Tag.add_or_create_for_upload(upload, "idempotent")

        await upload.fetch_related("tags")
        matching = [t for t in upload.tags if t.name == "idempotent"]
        assert len(matching) == 1


class TestTagRemoveTagFromUpload:
    """Tests for Tag.remove_tag_from_upload class method."""

    async def test_removes_tag_association(self, db):
        """The tag is removed from the upload's tag list."""
        _, upload = await _make_user_and_upload("r1")
        await Tag.add_or_create_for_upload(upload, "removeme")

        result = await Tag.remove_tag_from_upload(upload, "removeme")

        assert result is True
        await upload.fetch_related("tags")
        assert all(t.name != "removeme" for t in upload.tags)

    async def test_returns_false_when_tag_not_found(self, db):
        """Returns False when there is no tag with the given name."""
        _, upload = await _make_user_and_upload("r2")

        result = await Tag.remove_tag_from_upload(upload, "nonexistent")

        assert result is False

    async def test_deletes_orphaned_tag(self, db):
        """A tag with no remaining uploads is deleted from the database."""
        _, upload = await _make_user_and_upload("r3")
        await Tag.add_or_create_for_upload(upload, "orphan")

        await Tag.remove_tag_from_upload(upload, "orphan")

        assert await Tag.filter(name="orphan").count() == 0

    async def test_preserves_tag_shared_by_multiple_uploads(self, db):
        """A tag still referenced by another upload is not deleted."""
        _, upload1 = await _make_user_and_upload("r4a")
        _, upload2 = await _make_user_and_upload("r4b")
        await Tag.add_or_create_for_upload(upload1, "shared")
        await Tag.add_or_create_for_upload(upload2, "shared")

        await Tag.remove_tag_from_upload(upload1, "shared")

        assert await Tag.filter(name="shared").count() == 1

    async def test_sanitises_tag_name_on_remove(self, db):
        """Input is cleaned via make_clean_tag before lookup."""
        _, upload = await _make_user_and_upload("r5")
        await Tag.add_or_create_for_upload(upload, "sanitised-tag")

        # Passing mixed-case unsanitised version should still match
        result = await Tag.remove_tag_from_upload(upload, "Sanitised Tag")

        assert result is True

    async def test_raises_for_empty_tag_name(self, db):
        """ValueError raised when the cleaned name is empty."""
        _, upload = await _make_user_and_upload("r6")

        with pytest.raises(ValueError):
            await Tag.remove_tag_from_upload(upload, "")

    async def test_raises_for_only_invalid_chars(self, db):
        """ValueError raised when name contains only invalid characters."""
        _, upload = await _make_user_and_upload("r7")

        with pytest.raises(ValueError):
            await Tag.remove_tag_from_upload(upload, "!@#$")
