"""Tests for ETag and cache header utilities."""
import pytest
from unittest.mock import Mock
from fastapi import Request
from fastapi.testclient import TestClient
from fastapi.responses import Response

from app.models.uploads import UploadSerializer
from app.models.common.pagination import PaginationParams
from app.ui.common.etag import (
    get_paginated_gallery_etag,
    get_cache_headers,
    check_etag_and_return_304_if_match,
)


@pytest.fixture
def mock_request():
    request = Mock(spec=Request)
    request.session = {}
    return request


class TestGetPaginatedGalleryEtag:
    """Tests for get_paginated_gallery_etag function."""

    def test_returns_weak_etag_string(self, mock_request):
        """ETag should be a weak ETag formatted string."""
        uploads = []
        pagination = PaginationParams(page=1, page_size=24, count=0)

        etag = get_paginated_gallery_etag(
            request=mock_request,
            uploads=uploads,
            pagination=pagination,
            user_id=None,
        )

        assert isinstance(etag, str)
        assert etag.startswith('W/"')
        assert etag.endswith('"')

    def test_etag_includes_prefix(self, mock_request):
        """ETag should include the specified prefix."""
        uploads = []
        pagination = PaginationParams(page=1, page_size=24, count=0)

        etag = get_paginated_gallery_etag(
            request=mock_request,
            uploads=uploads,
            pagination=pagination,
            user_id=None,
            etag_prefix="gallery",
        )

        assert 'gallery-' in etag

    def test_etag_custom_prefix(self, mock_request):
        """ETag should use custom prefix if provided."""
        uploads = []
        pagination = PaginationParams(page=1, page_size=24, count=0)

        etag = get_paginated_gallery_etag(
            request=mock_request,
            uploads=uploads,
            pagination=pagination,
            user_id=None,
            etag_prefix="custom",
        )

        assert 'custom-' in etag

    def test_etag_changes_with_user(self, mock_request):
        """ETag should change when user context changes."""
        uploads = []
        pagination = PaginationParams(page=1, page_size=24, count=0)

        etag_user1 = get_paginated_gallery_etag(
            request=mock_request, uploads=uploads, pagination=pagination, user_id=1
        )
        etag_user2 = get_paginated_gallery_etag(
            request=mock_request, uploads=uploads, pagination=pagination, user_id=2
        )

        assert etag_user1 != etag_user2

    def test_etag_changes_with_pagination(self, mock_request):
        """ETag should change when pagination changes."""
        uploads = []

        etag_page1 = get_paginated_gallery_etag(
            request=mock_request,
            uploads=uploads,
            pagination=PaginationParams(page=1, page_size=24, count=100),
            user_id=None,
        )
        etag_page2 = get_paginated_gallery_etag(
            request=mock_request,
            uploads=uploads,
            pagination=PaginationParams(page=2, page_size=24, count=100),
            user_id=None,
        )

        assert etag_page1 != etag_page2

    def test_etag_stable_same_inputs(self, mock_request):
        """ETag should be stable for identical inputs."""
        uploads = []
        pagination = PaginationParams(page=1, page_size=24, count=0)

        etag1 = get_paginated_gallery_etag(
            request=mock_request, uploads=uploads, pagination=pagination, user_id=None
        )
        etag2 = get_paginated_gallery_etag(
            request=mock_request, uploads=uploads, pagination=pagination, user_id=None
        )

        assert etag1 == etag2

    def test_etag_includes_upload_ids(self, mock_request):
        """ETag should include upload IDs in signature."""
        pagination = PaginationParams(page=1, page_size=24, count=2)

        upload1 = Mock()
        upload1.id = 1
        upload1.updated_at = None
        upload1.image = None

        etag_with_upload = get_paginated_gallery_etag(
            request=mock_request, uploads=[upload1], pagination=pagination, user_id=None
        )
        etag_without_upload = get_paginated_gallery_etag(
            request=mock_request, uploads=[], pagination=pagination, user_id=None
        )

        assert etag_with_upload != etag_without_upload

    def test_etag_changes_with_flashes(self, mock_request):
        """ETag should change when session flash messages are present."""
        uploads = []
        pagination = PaginationParams(page=1, page_size=24, count=0)

        etag_no_flashes = get_paginated_gallery_etag(
            request=mock_request, uploads=uploads, pagination=pagination, user_id=None
        )

        mock_request.session["_flashes"] = [["info", "Something happened"]]
        etag_with_flashes = get_paginated_gallery_etag(
            request=mock_request, uploads=uploads, pagination=pagination, user_id=None
        )

        assert etag_no_flashes != etag_with_flashes


class TestGetCacheHeaders:
    """Tests for get_cache_headers function."""

    def test_returns_dict_with_required_headers(self):
        """Should return dict with Cache-Control, ETag, and Vary headers."""
        etag = 'W/"test-123"'

        headers = get_cache_headers(etag=etag)

        assert isinstance(headers, dict)
        assert "Cache-Control" in headers
        assert "ETag" in headers
        assert "Vary" in headers

    def test_cache_control_value(self):
        """Cache-Control should be set for private, must-revalidate with 60s max-age."""
        etag = 'W/"test-123"'

        headers = get_cache_headers(etag=etag)

        assert headers["Cache-Control"] == "private, max-age=60, must-revalidate"

    def test_etag_header_value(self):
        """ETag header should contain the provided etag value."""
        etag = 'W/"custom-abc123"'

        headers = get_cache_headers(etag=etag)

        assert headers["ETag"] == etag

    def test_vary_header_value(self):
        """Vary header should be set to Cookie since cache varies by user."""
        etag = 'W/"test-123"'

        headers = get_cache_headers(etag=etag)

        assert headers["Vary"] == "Cookie"


class TestCheckEtagAndReturn304IfMatch:
    """Tests for check_etag_and_return_304_if_match function."""

    def test_returns_none_without_if_none_match_header(self):
        """Should return None if If-None-Match header is not present."""
        from fastapi import FastAPI
        from httpx import AsyncClient

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            result = check_etag_and_return_304_if_match(request, 'W/"test-123"')
            return {"result": result}

        client = TestClient(app)
        response = client.get("/test")

        assert response.status_code == 200

    def test_returns_none_with_non_matching_etag(self):
        """Should return None if If-None-Match doesn't match ETag."""
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            result = check_etag_and_return_304_if_match(request, 'W/"abc123"')
            if result is not None:
                return result
            return {"result": None}

        client = TestClient(app)
        response = client.get("/test", headers={"If-None-Match": 'W/"xyz789"'})

        assert response.status_code == 200
        assert response.json() == {"result": None}

    def test_returns_304_with_matching_etag(self):
        """Should return 304 response if If-None-Match matches ETag."""
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            result = check_etag_and_return_304_if_match(request, 'W/"abc123"')
            if result is not None:
                return result
            return {"result": "not modified"}

        client = TestClient(app)
        response = client.get("/test", headers={"If-None-Match": 'W/"abc123"'})

        assert response.status_code == 304

    def test_returns_304_with_wildcard_etag(self):
        """Should return 304 if If-None-Match contains wildcard."""
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            result = check_etag_and_return_304_if_match(request, 'W/"abc123"')
            if result is not None:
                return result
            return {"result": "not modified"}

        client = TestClient(app)
        response = client.get("/test", headers={"If-None-Match": "*"})

        assert response.status_code == 304

    def test_304_response_includes_cache_headers(self):
        """304 response should include Cache-Control and ETag headers."""
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            result = check_etag_and_return_304_if_match(request, 'W/"abc123"')
            if result is not None:
                return result
            return {"result": "not modified"}

        client = TestClient(app)
        response = client.get("/test", headers={"If-None-Match": 'W/"abc123"'})

        assert response.status_code == 304
        assert "ETag" in response.headers
        assert "Cache-Control" in response.headers
        assert response.headers["ETag"] == 'W/"abc123"'

    def test_handles_multiple_etags_in_if_none_match(self):
        """Should match if any ETag in If-None-Match header matches."""
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            result = check_etag_and_return_304_if_match(request, 'W/"target123"')
            if result is not None:
                return result
            return {"result": "not modified"}

        client = TestClient(app)
        response = client.get(
            "/test",
            headers={"If-None-Match": 'W/"other1", W/"target123", W/"other2"'},
        )

        assert response.status_code == 304

    def test_etag_comparison_is_exact(self):
        """ETag comparison should be exact, not partial match."""
        from fastapi import FastAPI

        app = FastAPI()

        @app.get("/test")
        async def test_endpoint(request: Request):
            result = check_etag_and_return_304_if_match(request, 'W/"abc123"')
            if result is not None:
                return result
            return {"result": "not modified"}

        client = TestClient(app)
        # Similar but not matching ETag should not return 304
        response = client.get("/test", headers={"If-None-Match": 'W/"abc124"'})

        assert response.status_code == 200
        assert response.json() == {"result": "not modified"}
