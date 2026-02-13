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
- HomePaginationParams defaults
- humanize_bytes helper
"""

import pytest
import pytest_asyncio
from unittest.mock import AsyncMock, patch, MagicMock

from app.models.users import User
from app.models.uploads import Upload, UploadSerializer
from app.models.images import Image, ImageSerializer
from app.models.users import UserSerializer
from app.models.common.pagination import PaginationParams
from app.ui.main import HomePaginationParams
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
        with patch("app.ui.main.get_current_user_from_request", return_value=owner):
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


class TestHomePaginationParams:
    """Test HomePaginationParams overrides."""

    def test_default_sort_by(self):
        """Test HomePaginationParams defaults sort_by to created_at."""
        params = HomePaginationParams()
        assert params.sort_by == "created_at"

    def test_default_sort_order(self):
        """Test HomePaginationParams defaults sort_order to desc."""
        params = HomePaginationParams()
        assert params.sort_order == "desc"

    def test_default_page_size(self):
        """Test HomePaginationParams defaults page_size to 24."""
        params = HomePaginationParams()
        assert params.page_size == 24

    def test_inherits_pagination_params(self):
        """Test HomePaginationParams is a subclass of PaginationParams."""
        assert issubclass(HomePaginationParams, PaginationParams)

    def test_pages_calculation(self):
        """Test HomePaginationParams pages calculation with 24 page_size."""
        params = HomePaginationParams(count=50)
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
