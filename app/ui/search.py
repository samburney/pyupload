from typing import Annotated

from fastapi import APIRouter, Depends, Request
from fastapi.responses import Response
from tortoise.expressions import Q

from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User

from app.ui.common.breadcrumbs import Breadcrumbs
from app.ui.common.gallery import (
    GalleryPaginationDefaultParams,
    build_text_search_filter,
)
from app.ui.common.security import get_current_user
from app.ui.common.templating import templates
from app.ui.common.uploads import default_readable_query_filter


router = APIRouter(prefix="/search", tags=["search"])
breadcrumb_handler = Breadcrumbs(router=router, route_title="Search")

_PAGINATION_KEYS = {"page", "page_size", "sort_order", "sort_by", "infinite_scroll"}


@router.get("", response_class=Response)
async def search_index_get(
    request: Request,
    current_user: Annotated[User | None, Depends(get_current_user)],
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
    query: str | None = None,
) -> Response:
    """Render the search page and optional search results."""

    if not query:
        response = templates.TemplateResponse(
            request=request,
            name="search/index.html.j2",
            context={
                "current_user": current_user,
                "breadcrumbs": breadcrumbs.get_all(),
            },
        )

        return response

    uploads_query = build_text_search_filter(query, user=current_user)
    uploads_query &= default_readable_query_filter(user=current_user)

    filtered_upload_ids = await Upload.filter(uploads_query).distinct().values_list(
        "id",
        flat=True,
    )
    pagination.count = len(filtered_upload_ids)
    if current_user is not None:
        pagination.writable_count = await Upload.filter(
            Q(id__in=filtered_upload_ids),
            user_id=current_user.id,
        ).count()
    pagination.extra_params = {
        key: value
        for key, value in request.query_params.items()
        if key not in _PAGINATION_KEYS
    }

    upload_models = await Upload.paginate(
        **pagination.page_data(),
        query=Q(id__in=filtered_upload_ids),
    ).prefetch_related(*UPLOAD_PREFETCH_MODELS)
    uploads = [await UploadSerializer.from_tortoise_orm(u) for u in upload_models]

    is_htmx = bool(request.headers.get("HX-Request"))
    template_name = "search/results.html.j2"
    if is_htmx:
        template_name = "search/partials/results_output.html.j2"

    breadcrumbs.push(
        query,
        f'{request.url_for("search_index_get")}{pagination.page_url()}',
    )

    response = templates.TemplateResponse(
        request=request,
        name=template_name,
        context={
            "current_user": current_user,
            "uploads": uploads,
            "pagination": pagination,
            "breadcrumbs": breadcrumbs.get_all(),
            "enable_super_select": True,
        },
    )

    return response
