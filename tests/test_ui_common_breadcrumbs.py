"""Tests for the Breadcrumbs helper in app/ui/common/breadcrumbs.py.

Covers:
- Breadcrumb model accepts str and Starlette URL objects
- Breadcrumbs.handle_request returns a fresh instance per call (no shared state)
- handle_request seeds the stack with the router-level breadcrumb when route_title is set
- handle_request leaves the stack empty when route_title is None
- push appends a breadcrumb using the given URL or falls back to request.url
- pop removes the last breadcrumb
- replace swaps a breadcrumb at the given index
- get_all returns the current stack
- Integration: /gallery/ response includes breadcrumb nav markup
- Integration: /gallery/random response includes breadcrumb nav markup with "Random"
- Integration: / (root) response includes breadcrumb nav markup
"""

import pytest
from unittest.mock import Mock, MagicMock
from fastapi import APIRouter, Request
from starlette.datastructures import URL

from app.ui.common.breadcrumbs import Breadcrumb, Breadcrumbs


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_mock_request(url: str = "http://test/gallery/") -> Mock:
    request = Mock(spec=Request)
    request.url = URL(url)
    request.base_url = URL("http://test/")
    return request


def _make_router(prefix: str = "/gallery") -> APIRouter:
    return APIRouter(prefix=prefix)


# ---------------------------------------------------------------------------
# Breadcrumb model
# ---------------------------------------------------------------------------

class TestBreadcrumbModel:
    def test_accepts_string_url(self):
        b = Breadcrumb(title="Home", url="http://test/")
        assert str(b.url) == "http://test/"

    def test_accepts_starlette_url(self):
        b = Breadcrumb(title="Gallery", url=URL("http://test/gallery/"))
        assert "gallery" in str(b.url)

    def test_rejects_relative_url(self):
        with pytest.raises(Exception):
            Breadcrumb(title="Bad", url="/relative/path")


# ---------------------------------------------------------------------------
# Breadcrumbs factory — handle_request
# ---------------------------------------------------------------------------

class TestBreadcrumbsHandleRequest:
    def test_returns_new_instance_each_call(self):
        router = _make_router()
        handler = Breadcrumbs(router=router, route_title="Browse")
        req = _make_mock_request()

        instance_a = handler.handle_request(req)
        instance_b = handler.handle_request(req)

        assert instance_a is not instance_b

    def test_instances_have_independent_stacks(self):
        router = _make_router()
        handler = Breadcrumbs(router=router, route_title="Browse")
        req = _make_mock_request()

        instance_a = handler.handle_request(req)
        instance_b = handler.handle_request(req)

        instance_a.push("Extra")
        assert len(instance_a.get_all()) == 2
        assert len(instance_b.get_all()) == 1

    def test_seeds_stack_with_route_title(self):
        router = _make_router()
        handler = Breadcrumbs(router=router, route_title="Browse")
        req = _make_mock_request()

        bc = handler.handle_request(req)

        assert len(bc.get_all()) == 1
        assert bc.get_all()[0].title == "Browse"

    def test_route_breadcrumb_url_is_absolute(self):
        router = _make_router(prefix="/gallery")
        handler = Breadcrumbs(router=router, route_title="Browse")
        req = _make_mock_request()

        bc = handler.handle_request(req)

        assert str(bc.get_all()[0].url).startswith("http://")

    def test_empty_stack_when_no_route_title(self):
        router = _make_router()
        handler = Breadcrumbs(router=router)
        req = _make_mock_request()

        bc = handler.handle_request(req)

        assert bc.get_all() == []

    def test_request_stored_on_instance(self):
        router = _make_router()
        handler = Breadcrumbs(router=router, route_title="Browse")
        req = _make_mock_request()

        bc = handler.handle_request(req)

        assert bc.request is req


# ---------------------------------------------------------------------------
# push / pop / replace / get_all
# ---------------------------------------------------------------------------

class TestBreadcrumbsMutation:
    def _instance(self, url: str = "http://test/gallery/") -> Breadcrumbs:
        router = _make_router()
        handler = Breadcrumbs(router=router, route_title="Browse")
        return handler.handle_request(_make_mock_request(url))

    def test_push_appends_with_explicit_url(self):
        bc = self._instance()
        bc.push("Random", URL("http://test/gallery/random"))
        assert len(bc.get_all()) == 2
        assert bc.get_all()[1].title == "Random"

    def test_push_falls_back_to_request_url(self):
        bc = self._instance("http://test/gallery/random")
        bc.push("Random")
        crumb = bc.get_all()[1]
        assert "random" in str(crumb.url)

    def test_push_accepts_starlette_url(self):
        bc = self._instance()
        bc.push("Random", URL("http://test/gallery/random"))
        assert bc.get_all()[1].title == "Random"

    def test_push_accepts_string_url(self):
        bc = self._instance()
        bc.push("Random", "http://test/gallery/random")
        assert bc.get_all()[1].title == "Random"

    def test_pop_removes_last(self):
        bc = self._instance()
        bc.push("Random", URL("http://test/gallery/random"))
        assert len(bc.get_all()) == 2
        bc.pop()
        assert len(bc.get_all()) == 1

    def test_pop_empty_raises(self):
        router = _make_router()
        handler = Breadcrumbs(router=router)
        bc = handler.handle_request(_make_mock_request())
        with pytest.raises(IndexError):
            bc.pop()

    def test_replace_swaps_at_index(self):
        bc = self._instance()
        bc.replace(0, "Home", "http://test/")
        assert bc.get_all()[0].title == "Home"

    def test_replace_out_of_bounds_raises(self):
        bc = self._instance()
        with pytest.raises(IndexError):
            bc.replace(5, "Nope")

    def test_get_all_returns_list_of_breadcrumbs(self):
        bc = self._instance()
        result = bc.get_all()
        assert isinstance(result, list)
        assert all(isinstance(item, Breadcrumb) for item in result)


# ---------------------------------------------------------------------------
# Integration — breadcrumbs present in rendered responses
# ---------------------------------------------------------------------------

class TestBreadcrumbsIntegration:
    @pytest.mark.anyio
    async def test_gallery_index_includes_breadcrumb_nav(self, client):
        response = await client.get("/gallery/")
        assert response.status_code == 200
        assert 'aria-label="Breadcrumb"' in response.text

    @pytest.mark.anyio
    async def test_gallery_index_breadcrumb_shows_browse(self, client):
        response = await client.get("/gallery/")
        assert response.status_code == 200
        assert "Browse" in response.text

    @pytest.mark.anyio
    async def test_gallery_random_includes_breadcrumb_nav(self, client):
        response = await client.get("/gallery/random")
        assert response.status_code == 200
        assert 'aria-label="Breadcrumb"' in response.text

    @pytest.mark.anyio
    async def test_gallery_random_breadcrumb_shows_random(self, client):
        response = await client.get("/gallery/random")
        assert response.status_code == 200
        assert "Random" in response.text

    @pytest.mark.anyio
    async def test_root_includes_breadcrumb_nav(self, client):
        response = await client.get("/")
        assert response.status_code == 200
        assert 'aria-label="Breadcrumb"' in response.text

    @pytest.mark.anyio
    async def test_last_breadcrumb_is_not_linked(self, client):
        """Current page breadcrumb should be bold text, not an anchor."""
        response = await client.get("/gallery/random")
        assert response.status_code == 200
        assert '<span class="font-semibold">Random</span>' in response.text
