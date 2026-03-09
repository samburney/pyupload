from typing import Annotated
from fastapi import APIRouter, Request, Depends
from tortoise.expressions import Q

from app.models.common.pagination import PaginationParams
from app.models.uploads import Upload, UploadSerializer

from app.lib.auth import get_current_user_from_request

from app.ui.common.templating import templates
from app.ui.common.etag import (
    get_paginated_gallery_etag,
    get_cache_headers,
    check_etag_and_return_304_if_match,
)


router = APIRouter(prefix='/gallery', tags=['gallery'])


class GalleryPaginationDefaultParams(PaginationParams):
    """Default pagination parameters for the home page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page_size: int = 24


@router.get('/')
async def gallery_index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
):
    """Render main gallery view"""

    current_user = await get_current_user_from_request(request)

    # If user is logged, include their private uploads
    # TODO: Make this a user configurable option
    if current_user:
        query = Q(private=False) | Q(user=current_user)
    else:
        query = Q(private=False)

    # Update item pagination parameter
    pagination.count = await Upload.filter(query).count()

    # Get uploads
    uploads_models = Upload.paginate(**pagination.page_data(), query=query) \
        .prefetch_related("user", "images", "tags", "collections")
    uploads = await UploadSerializer.from_queryset(uploads_models)

    # Template context
    context = {
        "current_user": current_user,
        "uploads": uploads,
        "pagination": pagination,
    }

    etag = get_paginated_gallery_etag(
        uploads=uploads,
        pagination=pagination,
        user_id=current_user.id if current_user else None,
    )

    # Check if client already has current version
    not_modified = check_etag_and_return_304_if_match(request, etag)
    if not_modified:
        return not_modified

    # Build response with cache headers
    response = templates.TemplateResponse(request, "gallery/index.html.j2", context=context)
    response.headers.update(get_cache_headers(etag=etag))

    return response
