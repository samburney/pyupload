"""
Tests for Upload pagination, deletion, image handling, and relational queries.

- PaginationMixin: paginate() and pages() methods with sorting
- Upload.delete() — DB record removal and file deletion callback
- Upload.is_image property and Upload.rotate_image() method
- Upload.get_with_relations() classmethod and Upload.user_collections() instance method
"""
import pytest
from unittest.mock import patch

from app.models.users import User
from app.models.uploads import Upload
from app.models.collections import Collection
from app.lib.config import get_app_config

config = get_app_config()


def _upload_kwargs(user, suffix: str = "") -> dict:
    """Minimal Upload.create kwargs for tests in this section."""
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


class TestUploadPagination:
    """Test Upload model pagination functionality (PaginationMixin)."""

    async def test_paginate_returns_queryset(self, db):
        """Test paginate method returns a filtered queryset."""
        user = await User.create(username="pageuser", email="page@example.com", is_registered=True, password="password")

        # Create 15 uploads
        for i in range(15):
             await Upload.create(
                user=user,
                description=f"File {i}",
                name=f"file{i}_20250101-000000_12345678",
                cleanname=f"file{i}",
                originalname=f"file{i}.txt",
                ext="txt",
                size=100,
                type="text/plain",
                extra=""
            )

        # Paginate: page 1, size 10
        page1 = await Upload.paginate(page=1, page_size=10, user=user)
        assert len(page1) == 10

        # Paginate: page 2, size 10
        page2 = await Upload.paginate(page=2, page_size=10, user=user)
        assert len(page2) == 5

    async def test_pages_calculation(self, db):
        """Test pages calculation method."""
        user = await User.create(username="pagecalc", email="calc@example.com", is_registered=True, password="password")

        # Create 25 uploads
        for i in range(25):
             await Upload.create(
                user=user,
                description=f"File {i}",
                name=f"file{i}",
                cleanname="file",
                originalname="file.txt",
                ext="txt",
                size=100,
                type="text/plain",
                extra=""
            )

        # Page size 10 -> 3 pages
        pages = await Upload.pages(page_size=10, user=user)
        assert pages == 3

        # Page size 5 -> 5 pages
        pages = await Upload.pages(page_size=5, user=user)
        assert pages == 5

        # Page size 100 -> 1 page
        pages = await Upload.pages(page_size=100, user=user)
        assert pages == 1

    async def test_pagination_sorting(self, db):
        """Test pagination sorting arguments."""
        user = await User.create(username="pagesort", email="sort@example.com", is_registered=True, password="password")

        # Create 3 uploads with different sizes
        u1 = await Upload.create(user=user, description="Sort test", name="small", cleanname="small", originalname="s.txt", ext="txt", size=10, type="text/plain", extra="")
        u2 = await Upload.create(user=user, description="Sort test", name="medium", cleanname="medium", originalname="m.txt", ext="txt", size=20, type="text/plain", extra="")
        u3 = await Upload.create(user=user, description="Sort test", name="large", cleanname="large", originalname="l.txt", ext="txt", size=30, type="text/plain", extra="")

        # Sort by size asc
        asc = await Upload.paginate(page=1, page_size=10, sort_by="size", sort_order="asc", user=user)
        assert asc[0].id == u1.id
        assert asc[2].id == u3.id

        # Sort by size desc
        desc = await Upload.paginate(page=1, page_size=10, sort_by="size", sort_order="desc", user=user)
        assert desc[0].id == u3.id
        assert desc[2].id == u1.id

class TestUploadDelete:
    """Tests for Upload.delete()."""

    async def test_delete_removes_db_record(self, db, tmp_path):
        """delete() must remove the database record."""
        with patch.object(config, "storage_path", tmp_path):
            user = await User.create(
                username="deltest",
                email="deltest@example.com",
                password="pw",
                fingerprint_hash="fp-del",
            )
            upload = await Upload.create(
                user=user,
                description="",
                name="delfile_20250101-000000_a1b2c3d4",
                cleanname="delfile",
                originalname="delfile.txt",
                ext="txt",
                size=100,
                type="text/plain",
                extra="0",
            )
            upload_id = upload.id

            with patch("app.models.uploads.delete_file"):
                await upload.delete()

        assert await Upload.get_or_none(id=upload_id) is None

    async def test_delete_calls_delete_file_with_filepath(self, db, tmp_path):
        """delete() must call delete_file with self.filepath."""
        with patch.object(config, "storage_path", tmp_path):
            user = await User.create(
                username="delpathtest",
                email="delpathtest@example.com",
                password="pw",
                fingerprint_hash="fp-delpath",
            )
            upload = await Upload.create(
                user=user,
                description="",
                name="pathfile_20250101-000000_b2c3d4e5",
                cleanname="pathfile",
                originalname="pathfile.txt",
                ext="txt",
                size=100,
                type="text/plain",
                extra="0",
            )
            expected_path = upload.filepath

            with patch("app.models.uploads.delete_file") as mock_delete:
                await upload.delete()

        mock_delete.assert_called_once_with(expected_path)

    async def test_delete_removes_db_record_even_when_file_missing(self, db, tmp_path):
        """delete() removes the DB record even if the file does not exist on disk."""
        with patch.object(config, "storage_path", tmp_path):
            user = await User.create(
                username="delmissing",
                email="delmissing@example.com",
                password="pw",
                fingerprint_hash="fp-delmissing",
            )
            upload = await Upload.create(
                user=user,
                description="",
                name="missing_20250101-000000_c3d4e5f6",
                cleanname="missing",
                originalname="missing.txt",
                ext="txt",
                size=100,
                type="text/plain",
                extra="0",
            )
            upload_id = upload.id

            # File was never created on disk — delete_file will log a warning but not raise
            await upload.delete()

        assert await Upload.get_or_none(id=upload_id) is None


class TestUploadImageProperty:
    """Test Upload model is_image property."""

    async def test_is_image_without_images(self, db):
        """Test is_image returns False when no images are linked."""
        user = await User.create(username="noimg_prop", email="noimg_prop@test.com", password="pw", fingerprint_hash="fp")
        upload = await Upload.create(
            user=user,
            description="No image",
            name="test_20250124-063307_a1b2c3d4",
            cleanname="test",
            originalname="test.txt",
            ext="txt",
            size=512,
            type="text/plain",
            extra="0",
        )

        # When images are not prefetched, accessing property should raise RuntimeError
        with pytest.raises(RuntimeError):
            _ = upload.is_image

        # Manually fetch with prefetch_related
        upload_fetched = await Upload.get(id=upload.id).prefetch_related("images")

        # Now it should be False, not raise error
        assert upload_fetched.is_image is False

    async def test_is_image_with_images(self, db):
        """Test is_image returns True when images are linked."""
        from app.models.images import Image

        user = await User.create(username="withimg_prop", email="withimg_prop@test.com", password="pw", fingerprint_hash="fp")
        upload = await Upload.create(
            user=user,
            description="With image",
            name="img_20250124-063307_a1b2c3d4",
            cleanname="img",
            originalname="img.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="0",
        )

        # Must provide required fields
        await Image.create(
            upload=upload,
            type="jpeg",
            width=800,
            height=600,
            bits=8,
            channels=3
        )

        # When images are not prefetched, accessing property should raise RuntimeError
        with pytest.raises(RuntimeError):
            _ = upload.is_image

        # Manually fetch with prefetch_related
        upload_fetched = await Upload.get(id=upload.id).prefetch_related("images")
        assert upload_fetched.is_image is True


class TestUploadRotateImage:
    """Tests for Upload.rotate_image()."""

    async def _create_image_upload(self, username: str, email: str, width: int = 100, height: int = 60) -> Upload:
        """Create a DB-backed upload with an Image record, prefetched and ready."""
        from app.models.images import Image

        user = await User.create(username=username, email=email, password="pw")
        upload = await Upload.create(
            user=user,
            description="",
            name="rottest",
            cleanname="rottest",
            originalname="rottest.jpg",
            ext="jpg",
            size=1000,
            type="image/jpeg",
            extra="0",
        )
        await Image.create(upload=upload, type="jpeg", width=width, height=height, bits=24, channels=3)
        return await Upload.get(id=upload.id).prefetch_related("images")

    async def test_raises_value_error_for_non_image_upload(self, db):
        """rotate_image must raise ValueError when the upload has no linked image."""
        user = await User.create(username="rotnoimage", email="rotnoimage@example.com", password="pw")
        upload = await Upload.create(
            user=user, description="", name="noimg", cleanname="noimg",
            originalname="noimg.txt", ext="txt", size=100, type="text/plain", extra="0",
        )
        upload = await Upload.get(id=upload.id).prefetch_related("images")

        with pytest.raises(ValueError, match="Cannot rotate a non-image"):
            await upload.rotate_image(90)

    async def test_returns_true_on_success(self, db, tmp_path):
        """rotate_image must return True after a successful rotation."""
        from unittest.mock import AsyncMock, patch
        from app.models.images import ImageMetadata

        upload = await self._create_image_upload("rotsucc", "rotsucc@example.com")
        img_path = tmp_path / "rottest.jpg"
        from PIL import Image as Pillow
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")

        mock_metadata = ImageMetadata(upload_id=upload.id, type="jpeg", width=60, height=100, bits=24, channels=3)
        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            with patch("app.models.uploads.do_image_rotation", new=AsyncMock(return_value=mock_metadata)):
                result = await upload.rotate_image(90)

        assert result is True

    async def test_updates_image_dimensions_in_db(self, db, tmp_path):
        """After rotation, the Image record in the DB must reflect the new dimensions."""
        from unittest.mock import AsyncMock, patch
        from app.models.images import Image, ImageMetadata

        upload = await self._create_image_upload("rotdims", "rotdims@example.com", width=100, height=60)
        img_path = tmp_path / "rottest.jpg"
        from PIL import Image as Pillow
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")

        mock_metadata = ImageMetadata(upload_id=upload.id, type="jpeg", width=60, height=100, bits=24, channels=3)
        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            with patch("app.models.uploads.do_image_rotation", new=AsyncMock(return_value=mock_metadata)):
                await upload.rotate_image(90)

        refreshed_image = await Image.filter(upload=upload).first()
        assert refreshed_image is not None
        assert refreshed_image.width == 60
        assert refreshed_image.height == 100

    async def test_updates_upload_size_in_db(self, db, tmp_path):
        """After rotation, the Upload.size field must be updated to the new file size."""
        from unittest.mock import AsyncMock, patch
        from app.models.images import ImageMetadata

        upload = await self._create_image_upload("rotsize", "rotsize@example.com")
        img_path = tmp_path / "rottest.jpg"
        from PIL import Image as Pillow
        Pillow.new("RGB", (100, 60), color="red").save(str(img_path), format="JPEG")
        file_size_on_disk = img_path.stat().st_size

        mock_metadata = ImageMetadata(upload_id=upload.id, type="jpeg", width=60, height=100, bits=24, channels=3)
        with patch.object(Upload, "filepath", new_callable=lambda: property(lambda self: img_path)):
            with patch("app.models.uploads.do_image_rotation", new=AsyncMock(return_value=mock_metadata)):
                await upload.rotate_image(90)

        refreshed_upload = await Upload.get(id=upload.id)
        assert refreshed_upload.size == file_size_on_disk


class TestUploadGetWithRelations:
    """Tests for Upload.get_with_relations classmethod."""

    async def test_returns_upload_for_valid_id(self, db):
        """get_with_relations returns the upload when the ID exists."""
        user = await User.create(username="gwr1", email="gwr1@example.com", password="pw")
        upload = await Upload.create(**_upload_kwargs(user, "gwr1"))

        result = await Upload.get_with_relations(id=upload.id)

        assert result is not None
        assert result.id == upload.id

    async def test_returns_none_for_nonexistent_id(self, db):
        """get_with_relations returns None when the ID does not exist."""
        result = await Upload.get_with_relations(id=999999)

        assert result is None

    async def test_prefetches_collections(self, db):
        """get_with_relations prefetches the collections relation without raising."""
        user = await User.create(username="gwr2", email="gwr2@example.com", password="pw")
        upload = await Upload.create(**_upload_kwargs(user, "gwr2"))
        collection = await Collection.create(user=user, name="My Pics", name_unique="my-pics")
        await upload.collections.add(collection)

        result = await Upload.get_with_relations(id=upload.id)

        assert result is not None
        # Access the prefetched relation — should not raise
        col_ids = [c.id for c in result.collections]
        assert collection.id in col_ids

    async def test_prefetches_tags(self, db):
        """get_with_relations prefetches the tags relation without raising."""
        from app.models.tags import Tag

        user = await User.create(username="gwr3", email="gwr3@example.com", password="pw")
        upload = await Upload.create(**_upload_kwargs(user, "gwr3"))
        await Tag.add_or_create_for_upload(upload, "gwr-tag")

        result = await Upload.get_with_relations(id=upload.id)

        assert result is not None
        tag_names = [t.name for t in result.tags]
        assert "gwr-tag" in tag_names


class TestUploadUserCollections:
    """Tests for Upload.user_collections instance method."""

    async def test_returns_collections_owned_by_user(self, db):
        """user_collections returns collections belonging to the specified user."""
        user = await User.create(username="uc1", email="uc1@example.com", password="pw")
        upload = await Upload.create(**_upload_kwargs(user, "uc1"))
        col = await Collection.create(user=user, name="My Set", name_unique="my-set")
        await upload.collections.add(col)

        qs = upload.user_collections(user)
        results = await qs

        assert len(results) == 1
        assert results[0].id == col.id

    async def test_excludes_collections_owned_by_other_users(self, db):
        """user_collections excludes collections owned by other users."""
        owner = await User.create(username="uc2a", email="uc2a@example.com", password="pw")
        other = await User.create(username="uc2b", email="uc2b@example.com", password="pw")
        upload = await Upload.create(**_upload_kwargs(owner, "uc2"))

        owner_col = await Collection.create(user=owner, name="Owner Col", name_unique="owner-col")
        other_col = await Collection.create(user=other, name="Other Col", name_unique="other-col")
        await upload.collections.add(owner_col)
        await upload.collections.add(other_col)

        qs = upload.user_collections(owner)
        results = await qs

        result_ids = [r.id for r in results]
        assert owner_col.id in result_ids
        assert other_col.id not in result_ids

    async def test_returns_empty_when_upload_has_no_user_collections(self, db):
        """user_collections returns an empty queryset when the user has no collections on this upload."""
        user = await User.create(username="uc3", email="uc3@example.com", password="pw")
        upload = await Upload.create(**_upload_kwargs(user, "uc3"))

        qs = upload.user_collections(user)
        results = await qs

        assert len(results) == 0
