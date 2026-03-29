import random
import json

from datetime import datetime, timezone, timedelta
from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response
from fastapi.exceptions import HTTPException

from app.models.common.pagination import PaginationParams
from app.models.download_archives import DownloadArchive, DownloadArchiveSerializer, ArchiveStatusEnum
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User

from app.lib.config import get_app_config, logger
from app.lib.auth import get_current_user_from_request, get_current_authenticated_user

from app.ui.common.session import flash_message
from app.ui.common.templating import templates
from app.ui.common.uploads import default_readable_query_filter, get_writable_selected_upload_models, get_writable_selected_uploads
from app.ui.common.etag import (
    get_paginated_gallery_etag,
    get_cache_headers,
    check_etag_and_return_304_if_match,
)


config = get_app_config()
router = APIRouter(prefix='/gallery', tags=['gallery'])


class GalleryPaginationDefaultParams(PaginationParams):
    """Default pagination parameters for the home page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page_size: int = 24
    writable_count: int | None = None


@router.get('/', response_class=Response)
@router.get('/index', response_class=Response)
async def gallery_index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
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

    # Get selected uploads
    selected_uploads: list[UploadSerializer] = await get_writable_selected_uploads(current_user, selected_ids, super_selected, deselected_ids)

    # Match selected uploads against any existing DownloadArchives for this user
    selected_upload_ids = sorted(upload.id for upload in selected_uploads)
    download_archive = None
    download_archive_expires_at = datetime.now(tz=timezone.utc) - timedelta(hours=config.archive_max_age_hours)
    download_archive_models = await DownloadArchive.filter(user=current_user,
                                                          created_at__gt=download_archive_expires_at,
                                                          status__not=ArchiveStatusEnum.failed,
                                                          upload_ids=selected_upload_ids
                                                          ) \
                                                    .order_by("-created_at") \
                                                    .prefetch_related("user")
    
    # If there's multiple, just get the newest one
    if len(download_archive_models):
        download_archive_model = download_archive_models[0]
        download_archive = await DownloadArchiveSerializer.from_tortoise_orm(download_archive_model)

    # Template context
    context = {
        "current_user": current_user,
        "selected_uploads": selected_uploads,
        "download_archive": download_archive,
    }
    response = templates.TemplateResponse(
        request,
        "gallery/partials/sidebar.html.j2",
        context=context
    )

    return response


@router.post('/delete')
async def gallery_delete_selected_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
    ) -> Response:
    """
    Delete selected items and redirect back to requesting page
    
    We're using POST instead of DELETE to ensure we don't run out
    query_string space with a large number of selections.
    """

    # If this isn't a HTMX request, bail out now
    if not request.headers.get('hx-request', False):
        raise HTTPException(status_code=400, detail='Not a valid HTMX request')

    # Filter selected uploads to only those writable by the current_user
    upload_models: list[Upload] = await get_writable_selected_upload_models(current_user, selected_ids, super_selected, deselected_ids)
    if not upload_models:
        flash_message(request, "You do not have permission to delete any of the selected uploads.", "error")
        return templates.TemplateResponse(request, 'components/core/messages.html.j2', status_code=403)

    # Delete the selected uploads (use model instances to trigger custom delete with filesystem cleanup)
    deleted_count = 0
    try:
        for upload_model in upload_models:
            await upload_model.delete()
            deleted_count += 1
    except Exception as e:
        logger.exception("Failed to delete uploads: %s", e)
        flash_message(request, f"Deleted {deleted_count} of {len(upload_models)} upload{'s' if deleted_count != 1 else ''} before an error occurred. Please try again.", "error")
        return templates.TemplateResponse(request, 'components/core/messages.html.j2', status_code=500)

    # Determine redirect URL
    redirect_url = request.headers.get('referer', None)
    if not redirect_url:
        redirect_url = request.url_for('index_get')

    hx_location_dict: dict = {
        "source": request.headers.get('hx-trigger'),
        "path": redirect_url,
        "target": "#gallery-grid",
        "select": "#gallery-grid > *, #messages",
    }
    hx_location = json.dumps(hx_location_dict)

    hx_trigger_dict = {
        "close-modal": {"target": "#upload-delete-button"},
    }
    hx_trigger = json.dumps(hx_trigger_dict)

    headers = {
        "HX-Location": str(hx_location),
        "HX-Trigger": str(hx_trigger)
    }

    flash_message(request, f"{deleted_count} upload{'s' if deleted_count != 1 else ''} deleted successfully.")
    response = Response(status_code=204, headers=headers)

    return response



@router.get('/random', response_class=Response)
async def gallery_random_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
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


