from math import ceil
from pydantic import BaseModel 
from typing import TYPE_CHECKING, Any
from tortoise.queryset import QuerySet
from tortoise.expressions import Q

from app.models.common.base import _ModelBase


class PaginationParams(BaseModel):
    """Default pagination parameters."""

    page: int = 1
    page_size: int = 10
    sort_order: str = "asc"
    sort_by: str = "id"
    count: int = 0

    @property
    def pages(self) -> int:
        """Return the number of pages."""
        return ceil(self.count / self.page_size)

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
        *args: Q, **kwargs: Any
    ) -> "QuerySet[Any]":
        """Paginate user uploads."""
        
        offset = (page - 1) * page_size
        limit = page_size
        order = f'-{sort_by}' if sort_order == 'desc' else sort_by

        # Handle query argument if it's provided
        if query:
            qs = cls.filter(query)
        else:
            qs = cls.filter(*args, **kwargs)
        return qs.offset(offset).limit(limit).order_by(order)

    @classmethod
    async def pages(
        cls,
        page_size: int = 10,
        query: Q | None = None,
        *args: Q, **kwargs: Any
    ) -> int:
        """Paginate user uploads."""

        # Handle query argument if it's provided
        if query:
            qs = cls.filter(query)
        else:
            qs = cls.filter(*args, **kwargs)
        count = await qs.count()

        # Return 1 page if no items
        if count == 0:
            return 1
        pages = ceil(count / page_size)
        
        return pages
