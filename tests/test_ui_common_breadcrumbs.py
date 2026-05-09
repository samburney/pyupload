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
- register decorator stores builders by endpoint name
- populate_from_referrer calls the builder for the matching referrer route
- populate_from_referrer returns False when no referrer or no matching builder
- populate_from_referrer restores the stack when the builder raises
- populate_from_referrer ignores cross-origin referrers
- HX-Current-URL takes precedence over Referer
- Integration: /gallery/ response includes breadcrumb nav markup
- Integration: /gallery/random response includes breadcrumb nav markup with "Random"
- Integration: / (root) response includes breadcrumb nav markup
"""

import pytest
from unittest.mock import Mock
from fastapi import APIRouter, Request
from starlette.datastructures import URL
from starlette.routing import Match

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
        assert '<span class="font-semibold truncate block">Random</span>' in response.text


# ---------------------------------------------------------------------------
# Helpers shared by registry / populate tests
# ---------------------------------------------------------------------------

def _make_referrer_request(url: str = "http://test/view/1/file.txt", headers: dict | None = None, routes: list | None = None) -> Mock:
    request = Mock(spec=Request)
    request.url = URL(url)
    request.base_url = URL("http://test/")
    request.headers = headers or {}
    request.app = Mock()
    request.app.routes = routes or []
    return request


def _make_bc(request: Mock, route_title: str | None = None) -> Breadcrumbs:
    handler = Breadcrumbs(router=APIRouter(), route_title=route_title)
    return handler.handle_request(request)


def _make_matching_route(endpoint_name: str, path_params: dict | None = None) -> Mock:
    """Return a mock route that matches FULL and exposes the given endpoint name."""
    async def _endpoint(): pass
    _endpoint.__name__ = endpoint_name

    route = Mock()
    route.matches.return_value = (Match.FULL, {"endpoint": _endpoint, "path_params": path_params or {}})
    return route


# ---------------------------------------------------------------------------
# Breadcrumbs.register
# ---------------------------------------------------------------------------

class TestBreadcrumbsRegister:
    def test_register_stores_builder(self):
        async def builder(bc, **_): pass
        Breadcrumbs.register("_reg_test_single")(builder)
        try:
            assert Breadcrumbs._builders["_reg_test_single"] is builder
        finally:
            del Breadcrumbs._builders["_reg_test_single"]

    def test_register_stores_multiple_endpoint_names(self):
        async def builder(bc, **_): pass
        Breadcrumbs.register("_reg_test_a", "_reg_test_b")(builder)
        try:
            assert Breadcrumbs._builders["_reg_test_a"] is builder
            assert Breadcrumbs._builders["_reg_test_b"] is builder
        finally:
            del Breadcrumbs._builders["_reg_test_a"]
            del Breadcrumbs._builders["_reg_test_b"]

    def test_register_returns_original_function(self):
        async def builder(bc, **_): pass
        result = Breadcrumbs.register("_reg_test_ret")(builder)
        try:
            assert result is builder
        finally:
            del Breadcrumbs._builders["_reg_test_ret"]


# ---------------------------------------------------------------------------
# Breadcrumbs.populate_from_referrer
# ---------------------------------------------------------------------------

class TestPopulateFromReferrer:
    @pytest.mark.anyio
    async def test_returns_false_when_no_referrer_header(self):
        bc = _make_bc(_make_referrer_request(headers={}))
        assert await bc.populate_from_referrer() is False

    @pytest.mark.anyio
    async def test_returns_false_when_no_registered_builder_for_route(self):
        route = _make_matching_route("_pfr_test_unregistered_xyz")
        bc = _make_bc(_make_referrer_request(headers={"referer": "http://test/some/page"}, routes=[route]))
        assert await bc.populate_from_referrer() is False

    @pytest.mark.anyio
    async def test_calls_registered_builder_and_returns_true(self):
        called = {}

        async def builder(bc, path_params, query_params, context, **_):
            bc.stack = []
            bc.push("Built Crumb", "http://test/built")
            called["done"] = True

        Breadcrumbs._builders["_pfr_test_calls"] = builder
        try:
            route = _make_matching_route("_pfr_test_calls")
            bc = _make_bc(_make_referrer_request(headers={"referer": "http://test/some/page"}, routes=[route]))
            bc.stack = [Breadcrumb(title="Old", url="http://test/")]

            result = await bc.populate_from_referrer()

            assert result is True
            assert called.get("done") is True
            assert len(bc.stack) == 1
            assert bc.stack[0].title == "Built Crumb"
        finally:
            del Breadcrumbs._builders["_pfr_test_calls"]

    @pytest.mark.anyio
    async def test_restores_stack_when_builder_raises(self):
        async def failing_builder(bc, **_):
            raise RuntimeError("builder boom")

        Breadcrumbs._builders["_pfr_test_restore"] = failing_builder
        try:
            route = _make_matching_route("_pfr_test_restore")
            bc = _make_bc(_make_referrer_request(headers={"referer": "http://test/some/page"}, routes=[route]))
            bc.stack = [Breadcrumb(title="Saved", url="http://test/")]

            with pytest.raises(RuntimeError, match="builder boom"):
                await bc.populate_from_referrer()

            assert len(bc.stack) == 1
            assert bc.stack[0].title == "Saved"
        finally:
            del Breadcrumbs._builders["_pfr_test_restore"]

    @pytest.mark.anyio
    async def test_ignores_cross_origin_referrer(self):
        route = _make_matching_route("_pfr_test_cross_origin")
        bc = _make_bc(_make_referrer_request(headers={"referer": "http://evil.com/page"}, routes=[route]))
        assert await bc.populate_from_referrer() is False

    @pytest.mark.anyio
    async def test_hx_current_url_takes_precedence_over_referer(self):
        seen = {}

        async def hx_builder(bc, **_):
            bc.stack = []
            bc.push("HX Page", "http://test/hx-page")
            seen["source"] = "hx"

        Breadcrumbs._builders["_pfr_test_hx"] = hx_builder
        try:
            route = _make_matching_route("_pfr_test_hx")
            bc = _make_bc(_make_referrer_request(
                headers={"HX-Current-URL": "http://test/hx-page", "referer": "http://test/ref-page"},
                routes=[route],
            ))
            await bc.populate_from_referrer()
            assert seen.get("source") == "hx"
        finally:
            del Breadcrumbs._builders["_pfr_test_hx"]

    @pytest.mark.anyio
    async def test_passes_path_params_to_builder(self):
        received = {}

        async def builder(bc, path_params, **_):
            received["path_params"] = path_params

        Breadcrumbs._builders["_pfr_test_path_params"] = builder
        try:
            route = _make_matching_route("_pfr_test_path_params", path_params={"name": "my-slug"})
            bc = _make_bc(_make_referrer_request(headers={"referer": "http://test/things/my-slug"}, routes=[route]))
            await bc.populate_from_referrer()
            assert received["path_params"] == {"name": "my-slug"}
        finally:
            del Breadcrumbs._builders["_pfr_test_path_params"]

    @pytest.mark.anyio
    async def test_passes_query_params_to_builder(self):
        received = {}

        async def builder(bc, query_params, **_):
            received["query_params"] = query_params

        Breadcrumbs._builders["_pfr_test_query_params"] = builder
        try:
            route = _make_matching_route("_pfr_test_query_params")
            bc = _make_bc(_make_referrer_request(
                headers={"referer": "http://test/search?query=cats&sort=asc"},
                routes=[route],
            ))
            await bc.populate_from_referrer()
            assert received["query_params"] == {"query": "cats", "sort": "asc"}
        finally:
            del Breadcrumbs._builders["_pfr_test_query_params"]

    @pytest.mark.anyio
    async def test_passes_context_to_builder(self):
        received = {}

        async def builder(bc, context, **_):
            received["context"] = context

        Breadcrumbs._builders["_pfr_test_context"] = builder
        try:
            route = _make_matching_route("_pfr_test_context")
            bc = _make_bc(_make_referrer_request(headers={"referer": "http://test/page"}, routes=[route]))
            await bc.populate_from_referrer(context={"current_user": "alice"})
            assert received["context"] == {"current_user": "alice"}
        finally:
            del Breadcrumbs._builders["_pfr_test_context"]
