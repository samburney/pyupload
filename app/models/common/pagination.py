from math import ceil
from typing import TYPE_CHECKING, Any
from urllib.parse import urlencode

from pydantic import BaseModel
from tortoise.expressions import Q
from tortoise.queryset import QuerySet

from app.models.common.base import _ModelBase


class PaginationParams(BaseModel):
    """Default pagination parameters."""

    page: int = 1
    page_size: int = 10
    sort_order: str = "asc"
    sort_by: str = "id"
    count: int = 0
    infinite_scroll: bool = False
    extra_params: dict[str, str] = {}

    @property
    def pages(self) -> int:
        """Return the number of pages."""
        return ceil(self.count / self.page_size)

    def page_url(self, page: int | None = None) -> str:
        """Build a query string for the given page.

        Always includes extra_params and page. Other pagination params are only
        included when they differ from their declared defaults, keeping URLs clean.
        """

        if page is None:
            page = self.page

        params: dict[str, Any] = {**self.extra_params, "page": page}
        for key in ("page_size", "sort_order", "sort_by", "infinite_scroll"):
            value = getattr(self, key)
            if value != self.__class__.model_fields[key].default:
                params[key] = value

        return "?" + urlencode(params)

    def page_data(self) -> dict[str, Any]:
        """Return the page data."""

        return {
            "page": self.page,
            "page_size": self.page_size,
            "sort_order": self.sort_order,
            "sort_by": self.sort_by,
        }


class PaginationMixin(_ModelBase):
    """Mixin to add pagination support to models."""

    # Type hints referenced Model methods
    if TYPE_CHECKING:
        @classmethod
        def filter(cls, *args: "Q", **kwargs: Any) -> "QuerySet[Any]": ...  # type: ignore[misc]

    @classmethod
    def paginate(
        cls,
        page: int = 1,
        page_size: int = 10,
        sort_order: str = "asc",
        sort_by: str = "id",
        count: int = 0,
        query: Q | None = None,
        *args: Q,
        **kwargs: Any,
    ) -> "QuerySet[Any]":
        """Paginate user uploads."""

        offset = (page - 1) * page_size
        limit = page_size
        order = f"-{sort_by}" if sort_order == "desc" else sort_by

        # Handle query argument if it's provided
        if query is not None:
            qs = cls.filter(query)
        else:
            qs = cls.filter(*args, **kwargs)

        return qs.offset(offset).limit(limit).order_by(order)

    @classmethod
    async def pages(
        cls,
        page_size: int = 10,
        query: Q | None = None,
        *args: Q,
        **kwargs: Any,
    ) -> int:
        """Paginate user uploads."""

        # Handle query argument if it's provided
        if query is not None:
            qs = cls.filter(query)
        else:
            qs = cls.filter(*args, **kwargs)
        count = await qs.count()

        # Return 1 page if no items
        if count == 0:
            return 1

        pages = ceil(count / page_size)

        return pages
