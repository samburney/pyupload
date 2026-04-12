from typing import Annotated

from pydantic import BaseModel, TypeAdapter, HttpUrl
from pydantic.functional_validators import BeforeValidator
from starlette.datastructures import URL
from fastapi import Request, APIRouter


_validate_url = TypeAdapter(HttpUrl).validate_python


class Breadcrumb(BaseModel):
    title: str
    url: Annotated[HttpUrl, BeforeValidator(str)]


class Breadcrumbs:
    stack: list[Breadcrumb]
    router: APIRouter
    request: Request
    route_title: str | None

    def __init__(self, router: APIRouter, route_title: str | None = None) -> None:
        self.stack = []
        self.router = router
        self.route_title = route_title

    def handle_request(self, request: Request) -> "Breadcrumbs":
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
