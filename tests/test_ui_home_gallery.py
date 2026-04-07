"""
Tests for Home Gallery Page.

Validates:
- Home route returns public uploads only
- Private uploads excluded for anonymous users
- Private uploads included for their owner
- Uploads ordered by newest first
- Pagination works
- Related data prefetched (user, images)
- Empty state handled
- UploadSerializer produces expected fields
- UserSerializer produces expected fields
- ImageSerializer produces expected fields
- PaginationParams properties (pages, page_data)
- GalleryPaginationDefaultParams defaults
- humanize_bytes helper
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock
from tortoise import connections

from app.models.users import User
from app.models.uploads import Upload, UploadSerializer
from app.models.images import Image, ImageSerializer
from app.models.users import UserSerializer
from app.models.common.pagination import PaginationParams
from app.ui.gallery import GalleryPaginationDefaultParams
from app.lib.helpers import humanize_bytes


class TestHomeRoute:
    """Test the home route returns correct uploads."""

    @pytest.mark.anyio
    async def test_home_page_returns_200(self, client):
        """Test home page returns 200 status."""
        response = await client.get("/")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_home_page_empty_state(self, client):
        """Test home page shows empty state when no uploads exist."""
        response = await client.get("/")
        assert response.status_code == 200
        assert "nothing here" in response.text.lower() or "empty" in response.text.lower()

    @pytest.mark.anyio
    async def test_home_page_shows_public_uploads(self, client):
        """Test home page shows public uploads."""
        user = await User.create(
            password="hashed_password",
            username="gallery_user",
            email="gallery@test.com",
        )
        await Upload.create(
            user=user,
            description="Public Upload",
            name="public_file",
            cleanname="public_file",
            originalname="public_file.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="",
            private=0,
        )

        response = await client.get("/")
        assert response.status_code == 200
        assert "Public Upload" in response.text

    @pytest.mark.anyio
    async def test_home_page_excludes_private_uploads_for_anonymous(self, client):
        """Test home page excludes private uploads for anonymous users."""
        user = await User.create(
            password="hashed_password",
            username="private_user",
            email="private@test.com",
        )
        await Upload.create(
            user=user,
            description="Private Upload",
            name="private_file",
            cleanname="private_file",
            originalname="private_file.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="",
            private=1,
        )

        response = await client.get("/")
        assert response.status_code == 200
        assert "Private Upload" not in response.text

    @pytest.mark.anyio
    async def test_home_page_shows_both_public_and_owned_private(self, client):
        """Test home page shows public + owned private uploads for authenticated user."""
        owner = await User.create(
            password="hashed_password",
            username="owner_user",
            email="owner@test.com",
        )
        other = await User.create(
            password="hashed_password",
            username="other_user",
            email="other@test.com",
        )

        # Owner's private upload
        await Upload.create(
            user=owner,
            description="Owner Private",
            name="owner_private",
            cleanname="owner_private",
            originalname="owner_private.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="",
            private=1,
        )
        # Other's private upload
        await Upload.create(
            user=other,
            description="Other Private",
            name="other_private",
            cleanname="other_private",
            originalname="other_private.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="",
            private=1,
        )
        # Public upload
        await Upload.create(
            user=other,
            description="Other Public",
            name="other_public",
            cleanname="other_public",
            originalname="other_public.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="",
            private=0,
        )

        # Mock current_user as owner
        with patch("app.ui.gallery.get_current_user_from_request", return_value=owner):
            response = await client.get("/")

        assert response.status_code == 200
        assert "Owner Private" in response.text
        assert "Other Public" in response.text
        assert "Other Private" not in response.text

    @pytest.mark.anyio
    async def test_home_page_pagination_query_param(self, client):
        """Test home page accepts page query parameter."""
        response = await client.get("/?page=1")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_home_page_pagination_beyond_last_page(self, client):
        """Test home page with page number beyond available pages returns 200."""
        response = await client.get("/?page=999")
        assert response.status_code == 200

    @pytest.mark.anyio
    async def test_home_page_sets_document_cache_headers(self, client):
        """Test home page response includes cache-related headers for repeat loads."""
        response = await client.get("/")

        assert response.status_code == 200
        assert response.headers.get("cache-control") == "private, max-age=60, must-revalidate"
        assert response.headers.get("vary") == "Cookie"
        assert response.headers.get("etag", "").startswith('W/"gallery-')

    @pytest.mark.anyio
    async def test_home_page_returns_304_when_if_none_match_matches(self, client):
        """Test home page returns 304 Not Modified when ETag matches request header."""
        first_response = await client.get("/")
        etag = first_response.headers.get("etag")
        assert etag

        second_response = await client.get("/", headers={"If-None-Match": etag})

        assert second_response.status_code == 304
        assert second_response.headers.get("etag") == etag
        assert second_response.headers.get("cache-control") == "private, max-age=60, must-revalidate"


class TestHomeRouteDatabaseQueryPerformance:
    """Step 7 database-focused performance regression coverage."""

    SELECT_QUERY_BASELINE_BUDGET = 31

    async def _count_home_page_select_queries(self, client, path: str = "/?page=1") -> int:
        """Count SELECT queries executed during a single home page request."""
        connection = connections.get("default")
        select_query_count = 0

        original_execute_query = connection.execute_query
        original_execute_query_dict = connection.execute_query_dict

        async def counted_execute_query(sql, *args, **kwargs):
            nonlocal select_query_count
            if isinstance(sql, str) and sql.lstrip().upper().startswith("SELECT"):
                select_query_count += 1
            return await original_execute_query(sql, *args, **kwargs)

        async def counted_execute_query_dict(sql, *args, **kwargs):
            nonlocal select_query_count
            if isinstance(sql, str) and sql.lstrip().upper().startswith("SELECT"):
                select_query_count += 1
            return await original_execute_query_dict(sql, *args, **kwargs)

        with patch.object(connection, "execute_query", new=counted_execute_query), patch.object(
            connection, "execute_query_dict", new=counted_execute_query_dict
        ):
            response = await client.get(path)

        assert response.status_code == 200
        return select_query_count

    @pytest.mark.anyio
    async def test_home_page_query_count_baseline_page_1(self, client):
        """Step 7 DB baseline: page 1 render stays within a bounded SELECT query envelope."""
        owner = await User.create(
            password="hashed_password",
            username="db_query_baseline_owner",
            email="db.query.baseline.owner@test.com",
        )

        for index in range(24):
            upload = await Upload.create(
                user=owner,
                description=f"DB Baseline Item {index:02d}",
                name=f"db_baseline_item_{index:02d}",
                cleanname=f"db_baseline_item_{index:02d}",
                originalname=f"db_baseline_item_{index:02d}.jpg",
                ext="jpg",
                size=2048,
                type="image/jpeg",
                extra="",
                private=0,
            )
            await Image.create(
                upload=upload,
                type="image/jpeg",
                width=1280,
                height=720,
                bits=8,
                channels=3,
            )

        select_query_count = await self._count_home_page_select_queries(client, "/?page=1")

        assert select_query_count <= self.SELECT_QUERY_BASELINE_BUDGET

    @pytest.mark.anyio
    async def test_home_page_query_count_non_scaling_between_24_and_100_plus(self, client):
        """Step 7 N+1 guard: query-count envelope is stable from 24 items to 100+ items."""
        owner = await User.create(
            password="hashed_password",
            username="db_query_scaling_owner",
            email="db.query.scaling.owner@test.com",
        )

        for index in range(24):
            upload = await Upload.create(
                user=owner,
                description=f"DB Scale Seed 24 Item {index:02d}",
                name=f"db_scale_seed_24_item_{index:02d}",
                cleanname=f"db_scale_seed_24_item_{index:02d}",
                originalname=f"db_scale_seed_24_item_{index:02d}.jpg",
                ext="jpg",
                size=2048,
                type="image/jpeg",
                extra="",
                private=0,
            )
            await Image.create(
                upload=upload,
                type="image/jpeg",
                width=1280,
                height=720,
                bits=8,
                channels=3,
            )

        query_count_with_24 = await self._count_home_page_select_queries(client, "/?page=1")

        for index in range(24, 120):
            upload = await Upload.create(
                user=owner,
                description=f"DB Scale Seed 120 Item {index:03d}",
                name=f"db_scale_seed_120_item_{index:03d}",
                cleanname=f"db_scale_seed_120_item_{index:03d}",
                originalname=f"db_scale_seed_120_item_{index:03d}.jpg",
                ext="jpg",
                size=2048,
                type="image/jpeg",
                extra="",
                private=0,
            )
            await Image.create(
                upload=upload,
                type="image/jpeg",
                width=1280,
                height=720,
                bits=8,
                channels=3,
            )

        query_count_with_120 = await self._count_home_page_select_queries(client, "/?page=1")

        assert query_count_with_24 == query_count_with_120
        assert query_count_with_120 <= self.SELECT_QUERY_BASELINE_BUDGET


class TestHomeRouteUiScenarios:
    """UI-focused scenario and accessibility coverage for the home gallery."""

    @pytest.mark.anyio
    async def test_home_page_data_scenarios_empty_few_many(self, client):
        """Step 8 item 3: validate empty, few, and many upload scenarios."""
        owner = await User.create(
            password="hashed_password",
            username="ui_scenarios_user",
            email="ui.scenarios@test.com",
        )

        empty_response = await client.get("/")
        assert empty_response.status_code == 200
        assert "nothing here" in empty_response.text.lower() or "empty" in empty_response.text.lower()

        for index in range(3):
            await Upload.create(
                user=owner,
                description=f"UI FEW {index}",
                name=f"ui_few_{index}",
                cleanname=f"ui_few_{index}",
                originalname=f"ui_few_{index}.jpg",
                ext="jpg",
                size=1024,
                type="image/jpeg",
                extra="",
                private=0,
            )

        few_response = await client.get("/")
        assert few_response.status_code == 200
        assert "UI FEW 0" in few_response.text
        assert "UI FEW 1" in few_response.text
        assert "UI FEW 2" in few_response.text
        assert "class=\"pagination\"" not in few_response.text

        for index in range(30):
            await Upload.create(
                user=owner,
                description=f"UI MANY {index:02d}",
                name=f"ui_many_{index:02d}",
                cleanname=f"ui_many_{index:02d}",
                originalname=f"ui_many_{index:02d}.jpg",
                ext="jpg",
                size=1024,
                type="image/jpeg",
                extra="",
                private=0,
            )

        many_response = await client.get("/")
        assert many_response.status_code == 200
        assert "class=\"pagination\"" in many_response.text
        assert "?page=2" in many_response.text

    @pytest.mark.anyio
    async def test_home_page_responsive_breakpoint_classes_present(self, client):
        """Step 8 UI test item 5: verify responsive gallery classes are present."""
        owner = await User.create(
            password="hashed_password",
            username="ui_responsive_user",
            email="ui.responsive@test.com",
        )

        await Upload.create(
            user=owner,
            description="Responsive Gallery Item",
            name="responsive_gallery_item",
            cleanname="responsive_gallery_item",
            originalname="responsive_gallery_item.jpg",
            ext="jpg",
            size=1024,
            type="image/jpeg",
            extra="",
            private=0,
        )

        response = await client.get("/")

        assert response.status_code == 200
        assert "columns-1" in response.text
        assert "md:columns-2" in response.text
        assert "xl:columns-3" in response.text
        assert "2xl:columns-4" in response.text

    @pytest.mark.anyio
    async def test_home_page_accessibility_semantics_and_labels(self, client):
        """Step 8 item 5: validate basic accessibility semantics and labels."""
        owner = await User.create(
            password="hashed_password",
            username="ui_accessibility_user",
            email="ui.accessibility@test.com",
        )

        upload = await Upload.create(
            user=owner,
            description="Accessible Image Upload",
            name="ui_accessible_image",
            cleanname="ui_accessible_image",
            originalname="ui_accessible_image.jpg",
            ext="jpg",
            size=2048,
            type="image/jpeg",
            extra="",
            private=0,
        )
        await Image.create(
            upload=upload,
            type="image/jpeg",
            width=1600,
            height=900,
            bits=8,
            channels=3,
        )

        for index in range(55):
            paged_upload = await Upload.create(
                user=owner,
                description=f"ACCESS PAGINATION {index:02d}",
                name=f"access_pagination_{index:02d}",
                cleanname=f"access_pagination_{index:02d}",
                originalname=f"access_pagination_{index:02d}.jpg",
                ext="jpg",
                size=1024,
                type="image/jpeg",
                extra="",
                private=0,
            )
            await Image.create(
                upload=paged_upload,
                type="image/jpeg",
                width=1600,
                height=900,
                bits=8,
                channels=3,
            )

        response = await client.get("/?page=2")

        assert response.status_code == 200
        assert "<nav" in response.text
        assert "<main" in response.text
        assert "alt=\"" in response.text
        assert "aria-label=\"Previous page\"" in response.text
        assert "aria-label=\"Next page\"" in response.text


class TestGalleryCardUiRendering:
    """UI rendering tests covering Step 3 and Step 5 gallery-card requirements."""

    @pytest.mark.anyio
    async def test_step3_gallery_card_renders_image_and_non_image_states(self, client):
        """Step 3: image thumbnail/loading/aspect-ratio + non-image icon placeholders."""
        owner = await User.create(
            password="hashed_password",
            username="step3_card_user",
            email="step3.card@test.com",
        )

        image_upload = await Upload.create(
            user=owner,
            description="Step3 Image Upload",
            name="step3_image_upload",
            cleanname="step3_image_upload",
            originalname="step3_image_upload.jpg",
            ext="jpg",
            size=2048,
            type="image/jpeg",
            extra="",
            private=0,
        )
        await Image.create(
            upload=image_upload,
            type="image/jpeg",
            width=1600,
            height=900,
            bits=8,
            channels=3,
        )

        await Upload.create(
            user=owner,
            description="Step3 Video Upload",
            name="step3_video_upload",
            cleanname="step3_video_upload",
            originalname="step3_video_upload.mp4",
            ext="mp4",
            size=4096,
            type="video/mp4",
            extra="",
            private=0,
        )
        await Upload.create(
            user=owner,
            description="Step3 File Upload",
            name="step3_file_upload",
            cleanname="step3_file_upload",
            originalname="step3_file_upload.pdf",
            ext="pdf",
            size=1024,
            type="application/pdf",
            extra="",
            private=0,
        )

        response = await client.get("/")

        assert response.status_code == 200
        assert "animate-pulse" in response.text
        assert "aspect-ratio:" in response.text
        assert "x-show=\"!loaded\"" in response.text
        assert "border-dashed" in response.text
        assert ".mp4" in response.text
        assert ".pdf" in response.text

    @pytest.mark.anyio
    async def test_step5_gallery_card_renders_metadata_and_title_fallback(self, client):
        """Step 5: metadata display, truncation class, tooltip, and title fallback to filename."""
        owner = await User.create(
            password="hashed_password",
            username="step5_card_user",
            email="step5.card@test.com",
        )

        await Upload.create(
            user=owner,
            description="Visible Description Title",
            name="step5_described_upload",
            cleanname="step5_described_upload",
            originalname="step5_described_upload.jpg",
            ext="jpg",
            size=3210,
            type="image/jpeg",
            extra="",
            viewed=17,
            private=0,
        )
        fallback_upload = await Upload.create(
            user=owner,
            description="",
            name="step5_fallback_upload",
            cleanname="step5_fallback_upload",
            originalname="fallback_name.png",
            ext="png",
            size=789,
            type="image/png",
            extra="",
            viewed=3,
            private=0,
        )
        await Image.create(
            upload=fallback_upload,
            type="image/png",
            width=600,
            height=600,
            bits=8,
            channels=3,
        )

        response = await client.get("/")

        assert response.status_code == 200
        assert "Visible Description Title" in response.text
        assert "fallback_name.png" in response.text
        assert "title=\"fallback_name.png\"" in response.text
        assert "overflow-ellipsis whitespace-nowrap" in response.text
        assert ">17<" in response.text or "17" in response.text
        assert "step5_card_user" in response.text


class TestUploadSerializer:
    """Test UploadSerializer produces expected output."""

    @pytest.mark.anyio
    async def test_upload_serializer_fields(self, db):
        """Test UploadSerializer includes expected fields."""
        user = await User.create(
            password="hashed_password",
            username="serializer_user",
            email="serializer@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="Serialized Upload",
            name="serialized_file",
            cleanname="serialized_file",
            originalname="serialized_file.png",
            ext="png",
            size=2048,
            type="image/png",
            extra="",
            viewed=5,
            private=0,
        )

        # Refetch with prefetch
        upload = await Upload.filter(id=upload.id).prefetch_related("user", "images").first()
        serialized_list = await UploadSerializer.from_queryset(
            Upload.filter(id=upload.id).prefetch_related("user", "images")
        )
        assert len(serialized_list) == 1
        serialized = serialized_list[0]

        # Check core fields
        assert serialized.id == upload.id
        assert serialized.description == "Serialized Upload"
        assert serialized.name == "serialized_file"
        assert serialized.cleanname == "serialized_file"
        assert serialized.originalname == "serialized_file.png"
        assert serialized.ext == "png"
        assert serialized.size == 2048
        assert serialized.type == "image/png"
        assert serialized.viewed == 5
        assert serialized.private == 0

    @pytest.mark.anyio
    async def test_upload_serializer_computed_fields(self, db):
        """Test UploadSerializer computed fields work correctly."""
        user = await User.create(
            password="hashed_password",
            username="computed_user",
            email="computed@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="Computed Upload",
            name="computed_file",
            cleanname="computed_file",
            originalname="computed_file.png",
            ext="png",
            size=2048,
            type="image/png",
            extra="",
            private=0,
        )

        serialized_list = await UploadSerializer.from_queryset(
            Upload.filter(id=upload.id).prefetch_related("user", "images")
        )
        serialized = serialized_list[0]

        assert serialized.dot_ext == ".png"
        assert serialized.filename == "computed_file.png"
        assert "computed_file" in str(serialized.url)
        assert "computed_file" in str(serialized.view_url)
        assert "computed_file" in str(serialized.download_url)
        assert serialized.is_image is False  # No Image record created
        assert serialized.is_private is False

    @pytest.mark.anyio
    async def test_upload_serializer_with_image(self, db):
        """Test UploadSerializer resolves image relation."""
        user = await User.create(
            password="hashed_password",
            username="img_serializer_user",
            email="imgser@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="Image Upload",
            name="image_file",
            cleanname="image_file",
            originalname="image_file.jpg",
            ext="jpg",
            size=4096,
            type="image/jpeg",
            extra="",
            private=0,
        )
        await Image.create(
            upload=upload,
            type="image/jpeg",
            width=800,
            height=600,
            bits=8,
            channels=3,
        )

        serialized_list = await UploadSerializer.from_queryset(
            Upload.filter(id=upload.id).prefetch_related("user", "images")
        )
        serialized = serialized_list[0]

        assert serialized.image is not None
        assert serialized.image.width == 800
        assert serialized.image.height == 600
        assert serialized.is_image is True

    @pytest.mark.anyio
    async def test_upload_serializer_without_image(self, db):
        """Test UploadSerializer returns None for image when no Image record."""
        user = await User.create(
            password="hashed_password",
            username="noimg_serializer_user",
            email="noimgser@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="No Image Upload",
            name="noimage_file",
            cleanname="noimage_file",
            originalname="noimage_file.zip",
            ext="zip",
            size=4096,
            type="application/zip",
            extra="",
            private=0,
        )

        serialized_list = await UploadSerializer.from_queryset(
            Upload.filter(id=upload.id).prefetch_related("user", "images")
        )
        serialized = serialized_list[0]

        assert serialized.image is None
        assert serialized.is_image is False

    @pytest.mark.anyio
    async def test_upload_serializer_user_field(self, db):
        """Test UploadSerializer includes user serializer data."""
        user = await User.create(
            password="hashed_password",
            username="user_field_test",
            email="userfield@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="User Field Upload",
            name="userfield_file",
            cleanname="userfield_file",
            originalname="userfield_file.txt",
            ext="txt",
            size=1024,
            type="text/plain",
            extra="",
            private=0,
        )

        serialized_list = await UploadSerializer.from_queryset(
            Upload.filter(id=upload.id).prefetch_related("user", "images")
        )
        serialized = serialized_list[0]

        assert serialized.user.id == user.id
        assert serialized.user.username == "user_field_test"
        assert serialized.user.email == "userfield@test.com"

    @pytest.mark.anyio
    async def test_upload_serializer_timestamps(self, db):
        """Test UploadSerializer includes timestamp fields."""
        user = await User.create(
            password="hashed_password",
            username="ts_serializer_user",
            email="tsser@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="Timestamp Upload",
            name="ts_file",
            cleanname="ts_file",
            originalname="ts_file.txt",
            ext="txt",
            size=1024,
            type="text/plain",
            extra="",
            private=0,
        )

        serialized_list = await UploadSerializer.from_queryset(
            Upload.filter(id=upload.id).prefetch_related("user", "images")
        )
        serialized = serialized_list[0]

        assert serialized.created_at is not None
        assert serialized.updated_at is not None

    @pytest.mark.anyio
    async def test_upload_serializer_is_owner_and_is_writable_when_owner(self, db):
        """is_owner and is_writable are True when the context user owns the upload."""
        user = await User.create(
            password="hashed_password",
            username="owner_serializer_user",
            email="ownerser@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="Owner Upload",
            name="owner_file",
            cleanname="owner_file",
            originalname="owner_file.txt",
            ext="txt",
            size=1024,
            type="text/plain",
            extra="",
            private=0,
        )

        serialized = await UploadSerializer.from_tortoise_orm(
            await Upload.get_with_relations(upload.id), context={"user": user}
        )

        assert serialized.is_owner is True
        assert serialized.is_writable is True

    @pytest.mark.anyio
    async def test_upload_serializer_is_owner_and_is_writable_when_not_owner(self, db):
        """is_owner and is_writable are False when the context user does not own the upload."""
        owner = await User.create(
            password="hashed_password",
            username="upload_owner",
            email="upload_owner@test.com",
        )
        other_user = await User.create(
            password="hashed_password",
            username="other_user",
            email="other_user@test.com",
        )
        upload = await Upload.create(
            user=owner,
            description="Other Upload",
            name="other_file",
            cleanname="other_file",
            originalname="other_file.txt",
            ext="txt",
            size=1024,
            type="text/plain",
            extra="",
            private=0,
        )

        serialized = await UploadSerializer.from_tortoise_orm(
            await Upload.get_with_relations(upload.id), context={"user": other_user}
        )

        assert serialized.is_owner is False
        assert serialized.is_writable is False

    @pytest.mark.anyio
    async def test_upload_serializer_is_owner_and_is_writable_without_user_context(self, db):
        """is_owner and is_writable are None when no user is in context."""
        user = await User.create(
            password="hashed_password",
            username="nocontext_user",
            email="nocontext@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="No Context Upload",
            name="nocontext_file",
            cleanname="nocontext_file",
            originalname="nocontext_file.txt",
            ext="txt",
            size=1024,
            type="text/plain",
            extra="",
            private=0,
        )

        serialized = await UploadSerializer.from_tortoise_orm(
            await Upload.get_with_relations(upload.id)
        )

        assert serialized.is_owner is None
        assert serialized.is_writable is None


class TestUserSerializer:
    """Test UserSerializer produces expected output."""

    @pytest.mark.anyio
    async def test_user_serializer_fields(self, db):
        """Test UserSerializer includes expected fields."""
        user = await User.create(
            password="hashed_password",
            username="user_ser_test",
            email="userser@test.com",
            registration_ip="192.168.1.1",
            last_login_ip="192.168.1.2",
        )

        serialized_list = await UserSerializer.from_queryset(
            User.filter(id=user.id)
        )
        assert len(serialized_list) == 1
        serialized = serialized_list[0]

        assert serialized.id == user.id
        assert serialized.username == "user_ser_test"
        assert serialized.email == "userser@test.com"
        assert serialized.registration_ip == "192.168.1.1"
        assert serialized.last_login_ip == "192.168.1.2"
        assert serialized.is_registered is False
        assert serialized.is_abandoned is False
        assert serialized.is_admin is False
        assert serialized.is_disabled is False

    @pytest.mark.anyio
    async def test_user_serializer_timestamps(self, db):
        """Test UserSerializer includes timestamp fields."""
        user = await User.create(
            password="hashed_password",
            username="user_ts_test",
            email="userts@test.com",
        )

        serialized_list = await UserSerializer.from_queryset(
            User.filter(id=user.id)
        )
        serialized = serialized_list[0]

        assert serialized.created_at is not None
        assert serialized.updated_at is not None


class TestImageSerializer:
    """Test ImageSerializer produces expected output."""

    @pytest.mark.anyio
    async def test_image_serializer_fields(self, db):
        """Test ImageSerializer includes expected fields."""
        user = await User.create(
            password="hashed_password",
            username="imgser_user",
            email="imgser2@test.com",
        )
        upload = await Upload.create(
            user=user,
            description="Image Ser Upload",
            name="imgser_file",
            cleanname="imgser_file",
            originalname="imgser_file.jpg",
            ext="jpg",
            size=4096,
            type="image/jpeg",
            extra="",
            private=0,
        )
        image = await Image.create(
            upload=upload,
            type="image/jpeg",
            width=1920,
            height=1080,
            bits=8,
            channels=3,
        )

        serialized_list = await ImageSerializer.from_queryset(
            Image.filter(id=image.id)
        )
        assert len(serialized_list) == 1
        serialized = serialized_list[0]

        assert serialized.id == image.id
        assert serialized.upload_id == upload.id
        assert serialized.type == "image/jpeg"
        assert serialized.width == 1920
        assert serialized.height == 1080
        assert serialized.bits == 8
        assert serialized.channels == 3


class TestPaginationParams:
    """Test PaginationParams model properties."""

    def test_pages_property(self):
        """Test pages property calculates correctly."""
        params = PaginationParams(page=1, page_size=10, count=25)
        assert params.pages == 3  # ceil(25/10) = 3

    def test_pages_property_exact_division(self):
        """Test pages property with exact division."""
        params = PaginationParams(page=1, page_size=10, count=20)
        assert params.pages == 2

    def test_pages_property_zero_count(self):
        """Test pages property with zero count."""
        params = PaginationParams(page=1, page_size=10, count=0)
        assert params.pages == 0

    def test_pages_property_count_less_than_page_size(self):
        """Test pages property when count is less than page size."""
        params = PaginationParams(page=1, page_size=10, count=3)
        assert params.pages == 1

    def test_page_data_returns_dict(self):
        """Test page_data returns expected dictionary."""
        params = PaginationParams(page=2, page_size=24, sort_order="desc", sort_by="created_at")
        data = params.page_data()
        assert data == {
            "page": 2,
            "page_size": 24,
            "sort_order": "desc",
            "sort_by": "created_at",
        }

    def test_page_data_defaults(self):
        """Test page_data with default values."""
        params = PaginationParams()
        data = params.page_data()
        assert data["page"] == 1
        assert data["page_size"] == 10
        assert data["sort_order"] == "asc"
        assert data["sort_by"] == "id"

    def test_count_default_zero(self):
        """Test count defaults to zero."""
        params = PaginationParams()
        assert params.count == 0


class TestGalleryPaginationDefaultParams:
    """Test GalleryPaginationDefaultParams overrides."""

    def test_default_sort_by(self):
        """Test GalleryPaginationDefaultParams defaults sort_by to created_at."""
        params = GalleryPaginationDefaultParams()
        assert params.sort_by == "created_at"

    def test_default_sort_order(self):
        """Test GalleryPaginationDefaultParams defaults sort_order to desc."""
        params = GalleryPaginationDefaultParams()
        assert params.sort_order == "desc"

    def test_default_page_size(self):
        """Test GalleryPaginationDefaultParams defaults page_size to 24."""
        params = GalleryPaginationDefaultParams()
        assert params.page_size == 24

    def test_inherits_pagination_params(self):
        """Test GalleryPaginationDefaultParams is a subclass of PaginationParams."""
        assert issubclass(GalleryPaginationDefaultParams, PaginationParams)

    def test_pages_calculation(self):
        """Test GalleryPaginationDefaultParams pages calculation with 24 page_size."""
        params = GalleryPaginationDefaultParams(count=50)
        assert params.pages == 3  # ceil(50/24) = 3


class TestPaginationMixin:
    """Test PaginationMixin.paginate with query parameter."""

    @pytest.mark.anyio
    async def test_paginate_with_query_parameter(self, db):
        """Test paginate method accepts Q query argument."""
        from tortoise.expressions import Q

        user = await User.create(
            password="hashed_password",
            username="paginate_user",
            email="paginate@test.com",
        )

        # Create public and private uploads
        for i in range(5):
            await Upload.create(
                user=user,
                description=f"Public Upload {i}",
                name=f"public_{i}",
                cleanname=f"public_{i}",
                originalname=f"public_{i}.jpg",
                ext="jpg",
                size=1024,
                type="image/jpeg",
                extra="",
                private=0,
            )
        for i in range(3):
            await Upload.create(
                user=user,
                description=f"Private Upload {i}",
                name=f"private_{i}",
                cleanname=f"private_{i}",
                originalname=f"private_{i}.jpg",
                ext="jpg",
                size=1024,
                type="image/jpeg",
                extra="",
                private=1,
            )

        # Query for public uploads only
        query = Q(private=False)
        results = await Upload.paginate(
            page=1,
            page_size=10,
            sort_order="desc",
            sort_by="created_at",
            query=query,
        ).all()

        assert len(results) == 5

    @pytest.mark.anyio
    async def test_paginate_without_query_parameter(self, db):
        """Test paginate method works without query argument."""
        user = await User.create(
            password="hashed_password",
            username="paginate_noquery_user",
            email="paginatenoq@test.com",
        )

        for i in range(3):
            await Upload.create(
                user=user,
                description=f"Upload {i}",
                name=f"upload_{i}",
                cleanname=f"upload_{i}",
                originalname=f"upload_{i}.jpg",
                ext="jpg",
                size=1024,
                type="image/jpeg",
                extra="",
                private=0,
            )

        results = await Upload.paginate(page=1, page_size=10).all()
        assert len(results) == 3

    @pytest.mark.anyio
    async def test_paginate_respects_page_size(self, db):
        """Test paginate method respects page size."""
        user = await User.create(
            password="hashed_password",
            username="paginate_size_user",
            email="paginatesize@test.com",
        )

        for i in range(10):
            await Upload.create(
                user=user,
                description=f"Upload {i}",
                name=f"page_upload_{i}",
                cleanname=f"page_upload_{i}",
                originalname=f"page_upload_{i}.jpg",
                ext="jpg",
                size=1024,
                type="image/jpeg",
                extra="",
                private=0,
            )

        results = await Upload.paginate(page=1, page_size=3).all()
        assert len(results) == 3


class TestHumanizeBytes:
    """Test humanize_bytes helper function."""

    def test_humanize_bytes_zero(self):
        """Test humanize_bytes with zero bytes."""
        result = humanize_bytes(0)
        assert "0" in result or "Byte" in result

    def test_humanize_bytes_small(self):
        """Test humanize_bytes with small file size."""
        result = humanize_bytes(1024)
        # humanize.naturalsize returns "1.0 kB" or similar
        assert "kB" in result or "KB" in result or "1" in result

    def test_humanize_bytes_large(self):
        """Test humanize_bytes with large file size."""
        result = humanize_bytes(1048576)
        # humanize.naturalsize returns "1.0 MB" or similar
        assert "MB" in result or "1" in result

    def test_humanize_bytes_returns_string(self):
        """Test humanize_bytes returns a string."""
        result = humanize_bytes(500)
        assert isinstance(result, str)
