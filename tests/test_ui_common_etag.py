"""Tests for ETag and cache header utilities in app/ui/common/etag.py.

Covers:
- get_paginated_gallery_etag: weak ETag generation, prefix, stability, context sensitivity
- get_cache_headers: header names and values
- check_etag_and_return_304_if_match: If-None-Match matching, wildcard, multiple ETags
"""

import pytest
from unittest.mock import Mock
from fastapi import Request

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


def _request_with_if_none_match(value: str | None) -> Mock:
    """Build a mock Request with a specific If-None-Match header value."""
    request = Mock(spec=Request)
    request.headers = Mock()
    request.headers.get = Mock(return_value=value)
    return request


class TestGetPaginatedGalleryEtag:
    """Tests for get_paginated_gallery_etag."""

    def test_returns_weak_etag_string(self, mock_request):
        """ETag is a weak ETag formatted string."""
        etag = get_paginated_gallery_etag(
            request=mock_request,
            uploads=[],
            pagination=PaginationParams(page=1, page_size=24, count=0),
            user_id=None,
        )

        assert isinstance(etag, str)
        assert etag.startswith('W/"')
        assert etag.endswith('"')

    def test_default_prefix_is_gallery(self, mock_request):
        """ETag includes 'gallery-' prefix by default."""
        etag = get_paginated_gallery_etag(
            request=mock_request,
            uploads=[],
            pagination=PaginationParams(page=1, page_size=24, count=0),
            user_id=None,
        )

        assert "gallery-" in etag

    def test_custom_prefix_is_included(self, mock_request):
        """A custom etag_prefix is included in the ETag value."""
        etag = get_paginated_gallery_etag(
            request=mock_request,
            uploads=[],
            pagination=PaginationParams(page=1, page_size=24, count=0),
            user_id=None,
            etag_prefix="custom",
        )

        assert "custom-" in etag

    def test_etag_changes_with_user(self, mock_request):
        """ETag differs when user_id changes."""
        pagination = PaginationParams(page=1, page_size=24, count=0)

        etag_user1 = get_paginated_gallery_etag(request=mock_request, uploads=[], pagination=pagination, user_id=1)
        etag_user2 = get_paginated_gallery_etag(request=mock_request, uploads=[], pagination=pagination, user_id=2)

        assert etag_user1 != etag_user2

    def test_etag_changes_with_pagination(self, mock_request):
        """ETag differs when page number changes."""
        etag_page1 = get_paginated_gallery_etag(
            request=mock_request, uploads=[],
            pagination=PaginationParams(page=1, page_size=24, count=100), user_id=None,
        )
        etag_page2 = get_paginated_gallery_etag(
            request=mock_request, uploads=[],
            pagination=PaginationParams(page=2, page_size=24, count=100), user_id=None,
        )

        assert etag_page1 != etag_page2

    def test_etag_is_stable_for_identical_inputs(self, mock_request):
        """Same inputs produce the same ETag."""
        pagination = PaginationParams(page=1, page_size=24, count=0)
        kwargs = dict(request=mock_request, uploads=[], pagination=pagination, user_id=None)

        assert get_paginated_gallery_etag(**kwargs) == get_paginated_gallery_etag(**kwargs)

    def test_etag_changes_with_upload_content(self, mock_request):
        """ETag differs when the SelectionDetail-like upload list changes.

        The Mock object is not an UploadSerializer instance, so it takes the
        SelectionDetail branch in get_paginated_gallery_etag — only updated_at
        contributes to the signature. The test verifies that a non-empty list
        produces a different ETag than an empty list.
        """
        from datetime import datetime, timezone

        pagination = PaginationParams(page=1, page_size=24, count=2)

        upload = Mock()
        upload.updated_at = datetime(2025, 3, 1, tzinfo=timezone.utc)

        etag_with = get_paginated_gallery_etag(request=mock_request, uploads=[upload], pagination=pagination, user_id=None)
        etag_without = get_paginated_gallery_etag(request=mock_request, uploads=[], pagination=pagination, user_id=None)

        assert etag_with != etag_without

    def test_etag_changes_with_flash_messages(self, mock_request):
        """ETag differs when session flash messages are present."""
        pagination = PaginationParams(page=1, page_size=24, count=0)

        etag_no_flashes = get_paginated_gallery_etag(request=mock_request, uploads=[], pagination=pagination, user_id=None)

        mock_request.session["_flashes"] = [["info", "Something happened"]]
        etag_with_flashes = get_paginated_gallery_etag(request=mock_request, uploads=[], pagination=pagination, user_id=None)

        assert etag_no_flashes != etag_with_flashes

    async def test_etag_changes_with_uploadserializer_id(self, db):
        """ETag differs for two UploadSerializer items with different IDs (UploadSerializer branch).

        UploadSerializer items include upload.id in the signature, so two uploads
        with different IDs produce different ETags even when timestamps are equal.
        """
        from app.models.users import User
        from app.models.uploads import Upload, UploadSerializer

        user = await User.create(username="etaguser1", email="etag1@example.com", password="pw")
        upload_a = await Upload.create(
            user=user, name="etag_a", cleanname="etag_a", originalname="etag_a.txt",
            ext="txt", size=10, type="text/plain", extra="0", description="",
        )
        upload_b = await Upload.create(
            user=user, name="etag_b", cleanname="etag_b", originalname="etag_b.txt",
            ext="txt", size=10, type="text/plain", extra="0", description="",
        )

        ser_a = (await UploadSerializer.from_queryset(Upload.filter(id=upload_a.id).prefetch_related("user", "images", "tags")))[0]
        ser_b = (await UploadSerializer.from_queryset(Upload.filter(id=upload_b.id).prefetch_related("user", "images", "tags")))[0]

        mock_req = Mock(spec=Request)
        mock_req.session = {}
        pagination = PaginationParams(page=1, page_size=24, count=1)

        etag_a = get_paginated_gallery_etag(request=mock_req, uploads=[ser_a], pagination=pagination, user_id=None)
        etag_b = get_paginated_gallery_etag(request=mock_req, uploads=[ser_b], pagination=pagination, user_id=None)

        assert etag_a != etag_b


class TestGetCacheHeaders:
    """Tests for get_cache_headers."""

    def test_returns_all_required_headers(self):
        """Result contains Cache-Control, ETag, and Vary keys."""
        headers = get_cache_headers(etag='W/"test-123"')

        assert "Cache-Control" in headers
        assert "ETag" in headers
        assert "Vary" in headers

    def test_cache_control_value(self):
        """Cache-Control is set for private, must-revalidate with 60s max-age."""
        headers = get_cache_headers(etag='W/"test-123"')

        assert headers["Cache-Control"] == "private, max-age=60, must-revalidate"

    def test_etag_header_matches_input(self):
        """ETag header value matches the etag argument."""
        etag = 'W/"custom-abc123"'

        assert get_cache_headers(etag=etag)["ETag"] == etag

    def test_vary_header_is_cookie(self):
        """Vary header is set to Cookie since cache varies by user."""
        headers = get_cache_headers(etag='W/"test-123"')

        assert headers["Vary"] == "Cookie"


class TestCheckEtagAndReturn304IfMatch:
    """Tests for check_etag_and_return_304_if_match."""

    def test_returns_none_without_if_none_match_header(self):
        """Returns None when no If-None-Match header is present."""
        request = _request_with_if_none_match(None)

        assert check_etag_and_return_304_if_match(request, 'W/"abc123"') is None

    def test_returns_none_when_etag_does_not_match(self):
        """Returns None when If-None-Match header contains a different ETag."""
        request = _request_with_if_none_match('W/"xyz789"')

        assert check_etag_and_return_304_if_match(request, 'W/"abc123"') is None

    def test_returns_304_when_etag_matches(self):
        """Returns a 304 response when the ETag matches If-None-Match."""
        request = _request_with_if_none_match('W/"abc123"')

        response = check_etag_and_return_304_if_match(request, 'W/"abc123"')

        assert response is not None
        assert response.status_code == 304

    def test_returns_304_for_wildcard_if_none_match(self):
        """Returns a 304 response when If-None-Match is the wildcard '*'."""
        request = _request_with_if_none_match("*")

        response = check_etag_and_return_304_if_match(request, 'W/"abc123"')

        assert response is not None
        assert response.status_code == 304

    def test_304_response_includes_cache_headers(self):
        """304 response includes ETag and Cache-Control headers."""
        etag = 'W/"abc123"'
        request = _request_with_if_none_match(etag)

        response = check_etag_and_return_304_if_match(request, etag)

        assert response.status_code == 304
        assert response.headers["ETag"] == etag
        assert "Cache-Control" in response.headers

    def test_matches_any_etag_in_comma_separated_list(self):
        """Returns 304 if any ETag in a comma-separated If-None-Match matches."""
        request = _request_with_if_none_match('W/"other1", W/"target123", W/"other2"')

        response = check_etag_and_return_304_if_match(request, 'W/"target123"')

        assert response is not None
        assert response.status_code == 304

    def test_etag_comparison_is_exact(self):
        """A similar but non-identical ETag does not trigger 304."""
        request = _request_with_if_none_match('W/"abc124"')

        assert check_etag_and_return_304_if_match(request, 'W/"abc123"') is None
