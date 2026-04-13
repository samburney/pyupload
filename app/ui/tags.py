from typing import Annotated

from tortoise.functions import Count
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response, HTMLResponse

from app.lib.auth import get_current_user_from_request
from app.lib.helpers import make_clean_tag

from app.models.tags import Tag, TagSerializer
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User

from app.ui.common.breadcrumbs import Breadcrumbs
from app.ui.common.etag import get_paginated_gallery_etag, check_etag_and_return_304_if_match, get_cache_headers
from app.ui.common.errors import error_template_response
from app.ui.common.gallery import GalleryPaginationDefaultParams, TagSelectionDetail
from app.ui.common.security import get_current_authenticated_user
from app.ui.common.templating import templates
from app.ui.common.uploads import (
    default_readable_query_filter,
    get_readable_selected_upload_models,
)


router = APIRouter(prefix="/tags", tags=["tags"])
breadcrumb_handler = Breadcrumbs(router=router, route_title="Tags")


@router.get("", response_class=Response)
async def tags_index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Breadcrumbs = Depends(breadcrumb_handler.handle_request),
) -> Response:
    """Render main gallery view"""

    current_user = await get_current_user_from_request(request)

    tag_models = Tag.all().prefetch_related("uploads").annotate(upload_count=Count("uploads")).filter(upload_count__gt=0)
    tags = await TagSelectionDetail.from_queryset(tag_models, context={"user": current_user})

#    pagination_query = default_readable_query_filter(current_user)
#
#    # Update item pagination parameter
#    pagination.count = await Upload.filter(pagination_query).count()
#
#    # Get count of uploads owned by the current user, if any
#    if current_user:
#        pagination.writable_count = await Upload.filter(pagination_query).filter(user_id=current_user.id).count()
#
#    # Get uploads
#    uploads_models = Upload.paginate(**pagination.page_data(), query=pagination_query) \
#        .prefetch_related(*UPLOAD_PREFETCH_MODELS)
#    uploads = await UploadSerializer.from_queryset(uploads_models)
#
    # Template context
    context = {
        "current_user": current_user,
        "breadcrumbs": breadcrumbs.get_all(),
        "stacks": tags,
        "pagination": pagination,
    }
#
#    etag = get_paginated_gallery_etag(
#        request=request,
#        uploads=uploads,
#        pagination=pagination,
#        user_id=current_user.id if current_user else None,
#    )
#
#    # Check if client already has current version
#    not_modified = check_etag_and_return_304_if_match(request, etag)
#    if not_modified:
#        return not_modified
#
    # Build response with cache headers
    response = templates.TemplateResponse(request, "tags/index.html.j2", context=context)
#    response.headers.update(get_cache_headers(etag=etag))

    return response


@router.post("/suggestions", response_class=HTMLResponse)
async def get_tag_suggestions_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    tag_search: Annotated[str, Form()] = "",
    tag_name: Annotated[list[str], Form()] = [],
) -> Response:
    """Get tag suggestions for current upload, filtered by the current input value."""

    if tag_search == "":
        return Response(status_code=204)  # Return empty response if input is empty to avoid unnecessary database query

    # Pluraise variable name for clarity
    selected_tags = tag_name

    # Get tag suggestions
    new_tag = None
    suggested_tags = await Tag.all().filter(name__icontains=tag_search) \
        .exclude(name__in=selected_tags)[:5] \
        .values_list("name", flat=True)

    if tag_search not in suggested_tags:
        new_tag = make_clean_tag(tag_search)

    return templates.TemplateResponse(
        request,
        "components/tags/suggestions.html.j2",
        context={
            "new_tag": new_tag,
            "suggested_tags": suggested_tags,
        },
    )


@router.post("/update", response_class=Response)
async def upload_add_tag_post(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    request: Request,
    tag_name: Annotated[str, Form()],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Add a tag to an upload."""
    
    # Get uploads from database
    upload_models = await get_readable_selected_upload_models(
        current_user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )

    for upload_model in upload_models:
        try:
            # Add tag to the upload, creating the tag if it doesn't exist
            await Tag.add_or_create_for_upload(upload_model, tag_name)
            await upload_model.fetch_related("tags")

        except ValueError as e:
            return await error_template_response(request, [str(e)], status_code=400)

    if len(upload_models) == 1:
        tags = upload_models[0].tags
    else:
        tags = Tag.get_combined_for_uploads(upload_models)

    response = templates.TemplateResponse(
        request,
        "components/tags/macro_input.html.j2",
        context={"current_user": current_user, "tags": tags},
        status_code=200,
    )

    return response


@router.post("/delete", response_class=Response)
async def upload_remove_tag_delete(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    request: Request,
    tag_name: Annotated[str, Form()],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Remove a tag from an upload."""
    
    # Get upload from database
    upload_models = await get_readable_selected_upload_models(
        current_user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )

    for upload_model in upload_models:
        try:
            await Tag.remove_tag_from_upload(upload_model, tag_name)
            await upload_model.fetch_related("tags")

        except ValueError as e:
            return await error_template_response(request, [str(e)], status_code=400)

    if len(upload_models) == 1:
        tags = upload_models[0].tags
    else:
        tags = Tag.get_combined_for_uploads(upload_models)

    response = templates.TemplateResponse(
        request,
        "components/tags/macro_input.html.j2",
        context={"current_user": current_user, "tags": tags},
        status_code=200,
    )

    return response
