import re

from datetime import datetime, timezone, timedelta
from typing import Literal
from pydantic import BaseModel
from urllib.parse import urlparse

from tortoise.expressions import Q
from fastapi import Request
from fastapi.responses import Response

from app.lib.config import get_app_config

from app.models.collections import Collection, CollectionSerializerSelected
from app.models.download_archives import DownloadArchive, DownloadArchiveSerializer, ArchiveStatusEnum
from app.models.common.pagination import PaginationParams
from app.models.tags import Tag, TagSerializerSelected
from app.models.uploads import Upload, UploadSerializer
from app.models.users import User, UserSerializer

from app.ui.common.responses import error_template_response
from app.ui.common.templating import templates
from app.ui.common.uploads import get_writable_selected_uploads


config = get_app_config()


class GalleryPaginationDefaultParams(PaginationParams):
    """Default pagination parameters for the home page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page_size: int = 24
    writable_count: int | None = None


class SelectionDetail(BaseModel):
    """
    Detail model for an arbitrary list of Upload models.
    Mostly follows the API of the Upload model.
    """
    model_config = {"arbitrary_types_allowed": True}

    owners: list[UserSerializer]
    file_types: set[str]
    file_size: int
    viewed: int
    upload_count: int
    updated_at: datetime | None
    tags: list[TagSerializerSelected]
    collections: list[CollectionSerializerSelected]
    filtered_collections: list[Collection]
    is_writable: bool
    is_private: bool | Literal['partial']
    is_image: bool

    def __len__(self) -> int:
        return self.upload_count

    @classmethod
    def empty(cls) -> "SelectionDetail":
        return cls(
            owners=[],
            file_types=set(),
            file_size=0,
            viewed=0,
            upload_count=0,
            updated_at=None,
            tags=[],
            collections=[],
            filtered_collections=[],
            is_writable=False,
            is_private=False,
            is_image=False,
        )


def build_qs_filter(query_string: str) -> Q:
    """Create tortoiseorm compatible query from request query_string"""

    # parses ?uploader=alice&private=false&after=2024-01-01 etc.
    # Just a stub for now

    return Q()


async def _resolve_path_context_filter(path: str) -> Q | None:
    """Return Q for path-based view context, or Q(id__in=[]) on stale entity."""
    
    # Tags gallery view
    if m := re.match(r'^/tags/view/([^/]+)', path):
        tag = await Tag.get_or_none(name=m.group(1))
        return Q(tags__id=tag.id) if tag else Q(id__in=[])  # safe no-op if deleted
    
    # Collections gallery view
    if m := re.match(r'^/collections/view/([^/]+)', path):
        collection = await Collection.get_or_none(name_unique=m.group(1))
        return Q(collections__id=collection.id) if collection else Q(id__in=[])
    
    return None
    

async def get_request_context_filter(request: Request) -> Q | None:
    """Build context_filter from HX-Current-URL (path-based + query string)."""
    url = request.headers.get('hx-current-url')
    if not url:
        return None

    parsed = urlparse(url)
    filters: list[Q] = []

    # Path-based context (tag or collection view)
    path_filter = await _resolve_path_context_filter(parsed.path)
    if path_filter is not None:
        filters.append(path_filter)

    # Query string filters (stub — populates when build_qs_filter is implemented)
    qs_filter = build_qs_filter(parsed.query)
    if qs_filter:  # empty Q() is falsy; only append when non-trivial
        filters.append(qs_filter)

    if not filters:
        return None
    result = filters[0]
    for f in filters[1:]:
        result &= f
    return result


async def get_selection_detail(uploads: list[Upload] | list[UploadSerializer], user: User | None = None) -> SelectionDetail:
    """Build a SelectionDetail model from a provided list of Upload objects"""

    # Handle empty list
    if not len(uploads):
        raise ValueError("Cannot get selection detail from an empty list.")

    selection_owners: list[UserSerializer] = []
    seen_owners = set()
    selection_file_types = set()
    selection_file_size = 0
    selection_views = 0
    is_private: bool | Literal['partial'] = bool(uploads[0].private)

    # Get combined upload details
    for upload in uploads:
        upload_owner = upload.user

        # Selection owners
        if upload_owner.id not in seen_owners:
            seen_owners.add(upload_owner.id)
            if isinstance(upload_owner, UserSerializer):
                selection_owners.append(upload_owner)
            else:
                selection_owners.append(await UserSerializer.from_tortoise_orm(upload_owner))

        # Other computed values
        selection_file_types.add(upload.type)
        selection_file_size += upload.size
        selection_views += upload.viewed

        # Handle `is_private` partial logic
        if is_private != upload.private:
            is_private = 'partial'

    # If a user has been provided, calculate user-related detail for provided uploads
    selected_collections = []
    filtered_collections = []
    is_writable = False
    if user:
        selected_collections = await Collection.get_combined_for_uploads(user=user, uploads=uploads)

        # Get collections with filter applied, excluding those already linked to the upload
        selected_collection_ids = set(c.id for c in selected_collections)
        filtered_collections = await (
            Collection.filter(user=user)
            .exclude(id__in=selected_collection_ids)
            .limit(5)
            .order_by("name")
        )

        is_writable = all(o.id == user.id for o in selection_owners)

    selection_detail = SelectionDetail(
        owners=selection_owners,
        file_types=selection_file_types,
        file_size=selection_file_size,
        viewed=selection_views,
        upload_count=len(uploads),
        updated_at=max((u.updated_at for u in uploads), default=None),
        tags=Tag.get_combined_for_uploads(uploads),
        collections=selected_collections,
        filtered_collections=filtered_collections,
        is_writable=is_writable,
        is_private=is_private,
        is_image=all(u.is_image for u in uploads),
    )

    return selection_detail


async def render_multiselect_sidebar(
    request: Request,
    user: User,
    context_filter: Q | None = None,
    super_selected: bool = False,
    selected_ids: list[int] = [],
    deselected_ids: list[int] = [],
) -> Response:
    """Common function to render multiselect sidebar based on currently selected items"""

    # Get selected uploads
    selected_uploads: list[UploadSerializer] = await get_writable_selected_uploads(
        user=user,
        context_filter=context_filter,
        selected_ids=selected_ids,
        super_selected=super_selected,
        deselected_ids=deselected_ids,
    )

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
    download_archive_models = await DownloadArchive.filter(user=user,
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
    selection_detail = await get_selection_detail(selected_uploads, user)

    # Template context
    context = {
        "current_user": user,
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
