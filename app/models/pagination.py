from math import ceil
from pydantic import BaseModel 
from typing import Self, Any, Optional

from tortoise.queryset import Q, QuerySet

from app.models.base import _ModelBase


class PaginationParams(BaseModel):
    """Default pagination parameters."""

    page: int = 1
    page_size: int = 10
    sort_order: str = "asc"
    sort_by: str = "id"


class PaginationMixin(_ModelBase):
    """Mixin to add pagination support to models."""

    @classmethod
    def paginate(
        cls,
        page: int = 1,
        page_size: int = 10,
        sort_order: str = "asc",
        sort_by: str = "id",
        *args: Q, **kwargs: Any
    ) -> QuerySet[Self]:
        """Paginate user uploads."""
        
        offset = (page - 1) * page_size
        limit = page_size
        order = f'-{sort_by}' if sort_order == 'desc' else sort_by

        return cls.filter(*args, **kwargs).offset(offset).limit(limit).order_by(order)

    @classmethod
    async def pages(
        cls,
        page_size: int = 10,
        *args: Q, **kwargs: Any
    ) -> int:
        """Paginate user uploads."""

        count = await cls.filter(*args, **kwargs).count()
        pages = ceil(count / page_size)
        
        return pages
