import random
import re

from datetime import datetime, timedelta, timezone
from typing import Any, Literal
from urllib.parse import parse_qs, urlparse

from fastapi import Request
from fastapi.responses import Response
from pydantic import BaseModel, ConfigDict, Field
from tortoise.expressions import Q

from app.lib.auth import get_current_user_from_request
from app.lib.config import get_app_config
from app.lib.helpers import clean_text, split_filename

from app.models.collections import Collection, CollectionSerializerSelected
from app.models.common.pagination import PaginationParams
from app.models.download_archives import (
    ArchiveStatusEnum,
    DownloadArchive,
    DownloadArchiveSerializer,
)
from app.models.tags import Tag, TagSerializerSelected
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User, UserSerializer

from app.ui.common.breadcrumbs import Breadcrumbs
from app.ui.common.etag import (
    check_etag_and_return_304_if_match,
    get_cache_headers,
    get_paginated_gallery_etag,
)
from app.ui.common.responses import error_template_response
from app.ui.common.templating import templates
from app.ui.common.uploads import (
    default_readable_query_filter,
    get_writable_selected_uploads,
)


config = get_app_config()


class GalleryPaginationDefaultParams(PaginationParams):
    """Default pagination parameters for the home page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page_size: int = 24
    writable_count: int | None = None


class RandomGalleryPaginationParams(GalleryPaginationDefaultParams):
    """Pagination parameters for the random gallery view."""

    model_config = ConfigDict(populate_by_name=True)

    seed: int | None = Field(default=None, alias="ps")

    def model_post_init(self, _context: Any) -> None:
        if self.seed is None:
            self.seed = random.randint(0, 2**32)


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
    is_private: bool | Literal["partial"]
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


def build_text_search_filter(query: str, user: User | None = None) -> Q:
    """Build a Q filter matching uploads against a free-text search query."""

    q = (
        Q(description__icontains=query)
        | Q(name__icontains=query)
        | Q(originalname__icontains=query)
        | Q(ext__icontains=query)
        | Q(tags__name__iexact=clean_text(query, "-"))
    )

    name_part, ext_part = split_filename(query)
    if ext_part:
        q |= Q(originalname__iexact=name_part, ext__iexact=ext_part)

    if user is not None:
        q |= Q(collections__name__icontains=query, collections__user=user)

    return q


def build_qs_filter(query_string: str, user: User | None = None) -> Q | None:
    """Build a Q filter from a URL query string.

    Handles known filter parameters (?query=, and future additions).
    Returns None when no recognised parameters are present.
    """

    params = parse_qs(query_string)
    filters: list[Q] = []

    if query_values := params.get("query"):
        filters.append(build_text_search_filter(query_values[0], user))

    if not filters:
        return None

    result = filters[0]
    for f in filters[1:]:
        result &= f

    return result


async def _resolve_path_context_filter(path: str, user: User | None = None) -> Q | None:
    """Return Q for path-based view context, or Q(id__in=[]) on stale entity."""

    # User uploads gallery view
    if re.match(r"^/uploads$", path):
        return Q(user=user) if user else Q(id__in=[])

    # Tags gallery view
    if m := re.match(r"^/tags/view/([^/]+)", path):
        tag = await Tag.get_or_none(name=m.group(1))
        return Q(tags__id=tag.id) if tag else Q(id__in=[])  # safe no-op if deleted

    # Collections gallery view
    if m := re.match(r"^/collections/view/([^/]+)", path):
        collection = await Collection.get_or_none(name_unique=m.group(1))
        return Q(collections__id=collection.id) if collection else Q(id__in=[])

    return None


async def get_request_context_filter(request: Request, user: User | None = None) -> Q | None:
    """Build context_filter from HX-Current-URL (path-based + query string)."""

    url = request.headers.get("hx-current-url")
    if not url:
        return None

    parsed = urlparse(url)
    filters: list[Q] = []

    if user is None:
        user = await get_current_user_from_request(request)
    path_filter = await _resolve_path_context_filter(parsed.path, user)
    if path_filter is not None:
        filters.append(path_filter)

    # Query string filters
    qs_filter = build_qs_filter(parsed.query, user)
    if qs_filter is not None:
        filters.append(qs_filter)

    if not filters:
        return None

    result = filters[0]
    for f in filters[1:]:
        result &= f

    return result


async def get_selection_detail(
    uploads: list[Upload] | list[UploadSerializer],
    user: User | None = None,
) -> SelectionDetail:
    """Build a SelectionDetail model from a provided list of Upload objects"""

    # Handle empty list
    if not len(uploads):
        raise ValueError("Cannot get selection detail from an empty list.")

    selection_owners: list[UserSerializer] = []
    seen_owners = set()
    selection_file_types = set()
    selection_file_size = 0
    selection_views = 0
    is_private: bool | Literal["partial"] = bool(uploads[0].private)

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
            is_private = "partial"

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
    selected_ids: list[int] | None = None,
    deselected_ids: list[int] | None = None,
) -> Response:
    """Render the multiselect sidebar for the current selection."""

    if selected_ids is None:
        selected_ids = []

    if deselected_ids is None:
        deselected_ids = []

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
    download_archive_expires_at = datetime.now(tz=timezone.utc) - timedelta(
        hours=config.archive_max_age_hours
    )
    download_archive_models = await (
        DownloadArchive.filter(
            user=user,
            created_at__gt=download_archive_expires_at,
            status__not=ArchiveStatusEnum.failed,
            upload_ids=selected_upload_ids,
        )
        .order_by("-created_at")
        .prefetch_related("user")
    )

    # If there's multiple, just get the newest one
    if download_archive_models:
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
        request=request,
        name="gallery/partials/sidebar-content.html.j2",
        context=context,
    )

    return response


async def render_gallery_index(
    request: Request,
    pagination: GalleryPaginationDefaultParams,
    breadcrumbs: Breadcrumbs,
    context_filter: Q | None = None,
    user: User | None = None,
) -> Response:
    """Fetch uploads and render the gallery index template with ETag caching."""

    enable_super_select = False

    if user is None:
        user = await get_current_user_from_request(request)
    current_user = user
    pagination_query = default_readable_query_filter(current_user)

    if context_filter is not None:
        pagination_query &= context_filter
        enable_super_select = True

    pagination.count = await Upload.filter(pagination_query).count()

    if current_user:
        pagination.writable_count = await Upload.filter(pagination_query).filter(
            user_id=current_user.id
        ).count()

    uploads_models = Upload.paginate(
        **pagination.page_data(),
        query=pagination_query,
    ).prefetch_related(*UPLOAD_PREFETCH_MODELS)
    uploads = await UploadSerializer.from_queryset(uploads_models)

    context = {
        "current_user": current_user,
        "breadcrumbs": breadcrumbs.get_all(),
        "uploads": uploads,
        "pagination": pagination,
        "enable_super_select": enable_super_select,
    }
    response = templates.TemplateResponse(
        request=request,
        name="gallery/index.html.j2",
        context=context,
    )

    etag = get_paginated_gallery_etag(
        request=request,
        uploads=uploads,
        pagination=pagination,
        user_id=current_user.id if current_user else None,
    )

    not_modified = check_etag_and_return_304_if_match(request, etag)
    if not_modified:
        return not_modified

    response.headers.update(get_cache_headers(etag=etag))

    return response
