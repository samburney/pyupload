from datetime import datetime, timezone, timedelta
from typing import Literal

from pydantic import BaseModel
from fastapi import Request
from fastapi.responses import Response

from app.lib.config import get_app_config

from app.models.collections import Collection, CollectionSerializerSelected
from app.models.download_archives import DownloadArchive, DownloadArchiveSerializer, ArchiveStatusEnum
from app.models.tags import Tag, TagSerializerSelected
from app.models.uploads import UploadSerializer
from app.models.users import User, UserSerializer

from app.ui.common.errors import error_template_response
from app.ui.common.templating import templates
from app.ui.common.uploads import get_writable_selected_uploads


config = get_app_config()


class SelectionDetail(BaseModel):
    model_config = {"arbitrary_types_allowed": True}

    owners: list[UserSerializer]
    file_types: set[str]
    file_size: int
    tags: list[TagSerializerSelected]
    collections: list[CollectionSerializerSelected]
    filtered_collections: list[Collection]
    is_writable: bool
    is_private: bool | Literal['partial']
    is_image: bool


async def render_multiselect_sidebar(
    request: Request,
    current_user: User,
    super_selected: bool = False,
    selected_ids: list[int] = [],
    deselected_ids: list[int] = [],
) -> Response:
    """Common function to render multiselect sidebar based on currently selected items"""

    # Get selected uploads
    selected_uploads: list[UploadSerializer] = await get_writable_selected_uploads(current_user, selected_ids, super_selected, deselected_ids)
    if not selected_uploads:
        return await error_template_response(
            request=request,
            title="File(s) not found",
            error_messages=["You do not have permission to delete any of the selected uploads."],
            status_code=403,
        )

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

    # Get selection details
    selection_owners = []
    seen_owners = set()
    selection_file_types = set()
    selection_file_size = 0
    is_private: bool | Literal['partial'] = bool(selected_uploads[0].private)

    for upload in selected_uploads:
        # Selection owners
        if upload.user.id not in seen_owners:
            seen_owners.add(upload.user.id)
            selection_owners.append(upload.user)

        # Other computed values
        selection_file_types.add(upload.type)
        selection_file_size += upload.size

        # Handle `is_private` partial logic
        if is_private != upload.private:
            is_private = 'partial'

    # Get selected collections
    selected_collections = await Collection.get_combined_for_uploads(user=current_user, uploads=selected_uploads)

    # Get collections with filter applied, excluding those already linked to the upload
    selected_collection_ids = set(c.id for c in selected_collections)
    filtered_collections = await Collection.filter(user=current_user) \
        .exclude(id__in=selected_collection_ids).limit(5).order_by("name")

    selection_detail = SelectionDetail(
        owners=selection_owners,
        file_types=selection_file_types,
        file_size=selection_file_size,
        tags=Tag.get_combined_for_uploads(selected_uploads),
        collections=selected_collections,
        filtered_collections=filtered_collections,
        is_writable=all(o.id == current_user.id for o in selection_owners),
        is_private=is_private,
        is_image=all(u.is_image for u in selected_uploads),
    )

    # Template context
    context = {
        "current_user": current_user,
        "selected_uploads": selected_uploads,
        "download_archive": download_archive,
        "selection_detail": selection_detail,
    }
    response = templates.TemplateResponse(
        request,
        "gallery/partials/sidebar-content.html.j2",
        context=context
    )

    return response
