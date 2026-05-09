import urllib.parse
from typing import Annotated, Callable, Awaitable

from pydantic import BaseModel, TypeAdapter, HttpUrl
from pydantic.functional_validators import BeforeValidator
from starlette.datastructures import URL
from starlette.routing import Match
from fastapi import Request, APIRouter


_validate_url = TypeAdapter(HttpUrl).validate_python

BreadcrumbBuilder = Callable[..., Awaitable[None]]


class Breadcrumb(BaseModel):
    title: str
    url: Annotated[HttpUrl, BeforeValidator(str)]


class Breadcrumbs:
    """Breadcrumb trail builder with referrer-based reconstruction.

    Each router creates one shared Breadcrumbs instance (the "handler") and
    injects a fresh per-request instance via handle_request as a FastAPI
    dependency.

    Routes register their breadcrumb-building logic with @Breadcrumbs.register.
    The upload view page calls populate_from_referrer, which resolves the
    Referer / HX-Current-URL header to an endpoint name, looks up that
    endpoint's builder, and calls it to reconstruct the trail deterministically.
    This gives contextual breadcrumbs (e.g. Tags > landscape > filename) without
    storing any session state.

    Builder contract:
        async def my_builder(bc, path_params, query_params, context, **_) -> None
        - Reset bc.stack to [] and push the full trail from scratch.
        - Accept **_ to ignore params the builder doesn't need.
    """

    _builders: dict[str, BreadcrumbBuilder] = {}

    stack: list[Breadcrumb]
    router: APIRouter
    request: Request
    route_title: str | None

    def __init__(self, router: APIRouter, route_title: str | None = None) -> None:
        self.stack = []
        self.router = router
        self.route_title = route_title

    @classmethod
    def register(cls, *endpoint_names: str) -> Callable[[BreadcrumbBuilder], BreadcrumbBuilder]:
        """Decorator to register a breadcrumb builder for one or more endpoint names."""
        def decorator(fn: BreadcrumbBuilder) -> BreadcrumbBuilder:
            for name in endpoint_names:
                cls._builders[name] = fn
            return fn
        return decorator

    def handle_request(self, request: Request) -> "Breadcrumbs":
        """Return a fresh Breadcrumbs instance for this request.

        Seeds the stack with a single route-level crumb when route_title is set.
        Used as a FastAPI dependency: Depends(breadcrumb_handler.handle_request).
        """
        breadcrumbs = Breadcrumbs(router=self.router, route_title=self.route_title)
        breadcrumbs.request = request

        if breadcrumbs.route_title:
            route_url = f"{str(request.base_url).rstrip('/')}{self.router.prefix}/"
            route_breadcrumb = Breadcrumb(title=breadcrumbs.route_title, url=_validate_url(route_url))
            breadcrumbs.stack = [route_breadcrumb]

        return breadcrumbs

    def get_all(self) -> list[Breadcrumb]:
        return self.stack

    def _make_breadcrumb(self, title: str, url: str | URL | None = None) -> Breadcrumb:
        if not url:
            url = self.request.url

        return Breadcrumb(title=title, url=_validate_url(str(url)))

    def push(self, title: str, url: str | URL | None = None) -> None:
        self.stack.append(self._make_breadcrumb(title, url))

    def pop(self) -> None:
        self.stack.pop()

    def replace(self, index: int, title: str, url: str | URL | None = None) -> None:
        self.stack[index] = self._make_breadcrumb(title, url)

    def _resolve_referrer(self) -> tuple[str | None, dict, dict]:
        """Parse HX-Current-URL or Referer, match against app routes.
        Returns (endpoint_name, path_params, query_params) or (None, {}, {})."""
        prior_url = (
            self.request.headers.get("HX-Current-URL")
            or self.request.headers.get("referer")
        )
        if not prior_url:
            return None, {}, {}

        parsed = urllib.parse.urlparse(prior_url)
        if parsed.netloc and parsed.netloc != self.request.url.netloc:
            return None, {}, {}

        scope = {"type": "http", "method": "GET", "path": parsed.path}
        for route in self.request.app.routes:
            match, child_scope = route.matches(scope)
            if match == Match.FULL:
                name = getattr(child_scope.get("endpoint"), "__name__", None)
                if name:
                    query_params = dict(urllib.parse.parse_qsl(parsed.query))
                    return name, child_scope.get("path_params", {}), query_params

        return None, {}, {}

    async def populate_from_referrer(self, context: dict | None = None) -> bool:
        """Rebuild the breadcrumb stack using the registered builder for the referring page.

        Checks HX-Current-URL then Referer, matches the URL against app routes, and calls
        the registered builder for that endpoint. The builder resets the stack and rebuilds
        it deterministically from the referrer URL's path and query params.
        Returns True if a registered builder was found and called.
        """
        endpoint_name, path_params, query_params = self._resolve_referrer()
        builder = Breadcrumbs._builders.get(endpoint_name) if endpoint_name else None
        if not builder:
            return False

        saved, self.stack = self.stack, []
        try:
            await builder(self, path_params=path_params, query_params=query_params, context=context or {})
            return True
        except Exception:
            self.stack = saved
            raise
