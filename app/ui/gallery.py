import random

from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response
from fastapi.exceptions import HTTPException

from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User

from app.lib.auth import get_current_user_from_request
from app.lib.config import get_app_config

from app.ui.common.breadcrumbs import Breadcrumbs
from app.ui.common.gallery import (
    GalleryPaginationDefaultParams,
    RandomGalleryPaginationParams,
    render_gallery_index,
    render_multiselect_sidebar,
    get_request_context_filter,
)
from app.ui.common.security import get_current_authenticated_user
from app.ui.common.templating import templates
from app.ui.common.uploads import default_readable_query_filter


config = get_app_config()
router = APIRouter(prefix='/gallery', tags=['gallery'])
breadcrumb_handler = Breadcrumbs(router=router, route_title="Browse")


@router.get("", response_class=Response)
@router.get("/", response_class=Response)
@router.get("/index", response_class=Response)
async def gallery_index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render main gallery view"""

    return await render_gallery_index(request, pagination, breadcrumbs)


@router.get("/all", response_class=Response)
async def gallery_all_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render gallery sorted alphabetically with infinite scroll"""

    pagination.sort_by = "description"
    pagination.sort_order = "asc"
    pagination.infinite_scroll = True
    breadcrumbs.push(title="All", url=f"{request.base_url}all")
    return await render_gallery_index(request, pagination, breadcrumbs)


@router.get("/popular", response_class=Response)
async def gallery_popular_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render gallery sorted by view count"""

    pagination.sort_by = "viewed"
    pagination.sort_order = "desc"
    breadcrumbs.push(title="Popular", url=f"{request.base_url}popular")
    return await render_gallery_index(request, pagination, breadcrumbs)


@router.post('/update-selected')
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

    # Get request-based context filter
    context_filter = await get_request_context_filter(request, user=current_user)

    response = await render_multiselect_sidebar(
        request=request,
        context_filter=context_filter,
        user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )

    return response


@router.get('/random', response_class=Response)
async def gallery_random_get(
    request: Request,
    pagination: Annotated[RandomGalleryPaginationParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render random gallery view"""        

    pagination.infinite_scroll = True

    current_user = await get_current_user_from_request(request)
    pagination_query = default_readable_query_filter(current_user)

    # Update item pagination parameter
    upload_ids = await Upload.filter(pagination_query).limit(100_000).values_list("id", flat=True)
    pagination.count = len(upload_ids)

    # Get count of uploads owned by the current user, if any
    if current_user:
        pagination.writable_count = await Upload.filter(pagination_query).filter(user_id=current_user.id).count()

    # Get random rows
    rng = random.Random(pagination.seed)
    shuffled_ids = list(upload_ids)
    rng.shuffle(shuffled_ids)
    start = (pagination.page - 1) * pagination.page_size
    random_upload_ids = shuffled_ids[start:start + pagination.page_size]

    # Get uploads
    upload_models = Upload.filter(id__in=random_upload_ids) \
        .prefetch_related(*UPLOAD_PREFETCH_MODELS) \
        .order_by("-created_at")
    uploads = await UploadSerializer.from_queryset(upload_models)

    # Template context
    breadcrumbs.push("Random", request.url_for("gallery_random_get"))
    context = {
        "current_user": current_user,
        "breadcrumbs": breadcrumbs.get_all(),
        "uploads": uploads,
        "pagination": pagination,
    }
    response = templates.TemplateResponse(request, "gallery/index.html.j2", context=context)

    return response
