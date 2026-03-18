import random

from typing import Annotated, Optional
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response
from tortoise.expressions import Q

from app.models.common.pagination import PaginationParams
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User

from app.lib.auth import get_current_user_from_request, get_current_authenticated_user

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
    writable_count: int | None = None


def default_query_filter(current_user: Optional[User] = None) -> Q:
    # If user is logged, include their private uploads
    # TODO: Make this a user configurable option
    if current_user:
        query_filter = Q(private=False) | Q(user=current_user)
    else:
        query_filter = Q(private=False)

    return query_filter


@router.get('/')
@router.get('/index')
async def gallery_index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
):
    """Render main gallery view"""

    current_user = await get_current_user_from_request(request)
    pagination_query = default_query_filter(current_user)

    # Update item pagination parameter
    pagination.count = await Upload.filter(pagination_query).count()

    # Get count of uploads owned by the current user, if any
    if current_user:
        pagination.writable_count = await Upload.filter(pagination_query).filter(user_id=current_user.id).count()

    # Get uploads
    uploads_models = Upload.paginate(**pagination.page_data(), query=pagination_query) \
        .prefetch_related(*UPLOAD_PREFETCH_MODELS)
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


@router.post('/index')
async def gallery_index_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Render partial page updates when selected items are updated"""

    # Get Upload models for selected items
    # If Super Select mode is enable, get all and exclude deselected items.
    if super_selected:
        upload_models = Upload.filter(user=current_user, id__not_in=deselected_ids) \
            .prefetch_related(*UPLOAD_PREFETCH_MODELS)
    # Otherwise, only get selected items.
    else:
        upload_models = Upload.filter(user=current_user, id__in=selected_ids) \
            .prefetch_related(*UPLOAD_PREFETCH_MODELS)
    uploads = await UploadSerializer.from_queryset(upload_models, context={"user": current_user})

    # Template context
    context = {
        "current_user": current_user,
        "selected_uploads": uploads,
    }
    response = templates.TemplateResponse(
        request,
        "gallery/partials/sidebar.html.j2",
        context=context
    )

    return response


@router.get('/random')
async def gallery_random_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
):
    """Render random gallery view"""        

    current_user = await get_current_user_from_request(request)
    pagination_query = default_query_filter(current_user)

    # Update item pagination parameter
    upload_ids = await Upload.filter(pagination_query).values_list("id", flat=True)
    pagination.count = len(upload_ids)

    # Get count of uploads owned by the current user, if any
    if current_user:
        pagination.writable_count = await Upload.filter(pagination_query).filter(user_id=current_user.id).count()

    # Get random rows
    row_count = min(pagination.page_size, pagination.count)
    random_upload_ids = random.sample(upload_ids, row_count)

    # Get uploads
    upload_models = Upload.filter(id__in=random_upload_ids) \
        .prefetch_related(*UPLOAD_PREFETCH_MODELS)
    uploads = await UploadSerializer.from_queryset(upload_models)

    # Define breadcrumbs
    # TODO: Needs to be more automated...
    breadcrumbs = [
        {"url": "/gallery/random", "title": "Random"}
    ]

    # Template context
    context = {
        "current_user": current_user,
        "uploads": uploads,
        "pagination": pagination,
        "breadcrumbs": breadcrumbs,
    }
    response = templates.TemplateResponse(request, "gallery/random.html.j2", context=context)

    return response


