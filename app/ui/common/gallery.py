from datetime import datetime, timezone, timedelta
from typing import Literal

from pydantic import BaseModel
from tortoise_serializer import ContextType
from fastapi import Request
from fastapi.responses import Response

from app.lib.config import get_app_config

from app.models.collections import Collection, CollectionSerializerSelected
from app.models.download_archives import DownloadArchive, DownloadArchiveSerializer, ArchiveStatusEnum
from app.models.common.pagination import PaginationParams
from app.models.tags import Tag, TagSerializer, TagSerializerSelected
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User, UserSerializer

from app.ui.common.errors import error_template_response
from app.ui.common.templating import templates
from app.ui.common.uploads import default_readable_query_filter, get_writable_selected_uploads


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
        filtered_collections = await Collection.filter(user=user) \
            .exclude(id__in=selected_collection_ids).limit(5).order_by("name")
        
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


class TagSelectionDetail(TagSerializer):
    """A `TagSerializer` with `SelectionDetail` computed"""

    selection_detail: SelectionDetail

    @classmethod
    async def readable_uploads(cls, instance: Tag, context: ContextType) -> list[Upload]:
        """Fetch uploads for this tag readable by the current user (public + user's own private)."""

        user = context.get("user")
        upload_queryset = instance.uploads.filter(default_readable_query_filter(user)).prefetch_related(*UPLOAD_PREFETCH_MODELS)  # type: ignore[no-member]
        upload_models = await upload_queryset.all()

        return upload_models

    @classmethod
    async def writable_uploads(cls, instance: Tag, context: ContextType) -> list[Upload]:
        """Fetch uploads for this tag that are owned by (and thus writable by) the current user."""

        user = context.get("user")
        if not user:
            return []
        upload_queryset = instance.uploads.filter(user=user).prefetch_related(*UPLOAD_PREFETCH_MODELS)  # type: ignore[no-member]
        upload_models = await upload_queryset.all()

        return upload_models

    @classmethod
    async def resolve_selection_detail(cls, instance: Tag, context: ContextType) -> SelectionDetail:
        """Build a SelectionDetail from the tag's associated uploads."""

        user = context.get("user")

        uploads: list[Upload] = await cls.readable_uploads(instance, context)

        return await get_selection_detail(uploads=uploads, user=user)


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
    selection_detail = await get_selection_detail(selected_uploads, current_user)

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
