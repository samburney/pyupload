import random

from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response
from fastapi.exceptions import HTTPException

from app.models.common.pagination import PaginationParams
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User

from app.lib.auth import get_current_user_from_request, get_current_authenticated_user
from app.lib.config import get_app_config

from app.ui.common.breadcrumbs import Breadcrumbs
from app.ui.common.etag import (
    get_paginated_gallery_etag,
    get_cache_headers,
    check_etag_and_return_304_if_match,
)
from app.ui.common.gallery import render_multiselect_sidebar
from app.ui.common.templating import templates
from app.ui.common.uploads import default_readable_query_filter


config = get_app_config()
router = APIRouter(prefix='/gallery', tags=['gallery'])
breadcrumb_handler = Breadcrumbs(router=router, route_title="Browse")


class GalleryPaginationDefaultParams(PaginationParams):
    """Default pagination parameters for the home page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page_size: int = 24
    writable_count: int | None = None


@router.get("", response_class=Response)
@router.get("/", response_class=Response)
@router.get("/index", response_class=Response)
async def gallery_index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Breadcrumbs = Depends(breadcrumb_handler.handle_request),
) -> Response:
    """Render main gallery view"""

    current_user = await get_current_user_from_request(request)
    pagination_query = default_readable_query_filter(current_user)

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
        "breadcrumbs": breadcrumbs.get_all(),
        "uploads": uploads,
        "pagination": pagination,
    }

    etag = get_paginated_gallery_etag(
        request=request,
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


@router.post('')
async def gallery_handle_selected_upload_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Render partial page updates when selected items are updated"""

    # If this isn't a HTMX request, bail out now
    if not request.headers.get('hx-request', False):
        raise HTTPException(status_code=400, detail='Not a valid HTMX request')

    response = await render_multiselect_sidebar(
        request,
        current_user,
        super_selected,
        selected_ids,
        deselected_ids,
    )

    return response


@router.get('/random', response_class=Response)
async def gallery_random_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Breadcrumbs = Depends(breadcrumb_handler.handle_request),
) -> Response:
    """Render random gallery view"""        

    current_user = await get_current_user_from_request(request)
    pagination_query = default_readable_query_filter(current_user)

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

    # Template context
    breadcrumbs.push("Random", request.url_for("gallery_random_get"))
    context = {
        "current_user": current_user,
        "breadcrumbs": breadcrumbs.get_all(),
        "uploads": uploads,
        "pagination": pagination,
    }
    response = templates.TemplateResponse(request, "gallery/random.html.j2", context=context)

    return response
