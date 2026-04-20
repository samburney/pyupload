from typing import Any, Optional, cast

from fastapi import HTTPException

from tortoise.queryset import QuerySet
from tortoise.expressions import Q

from app.models.common.pagination import PaginationParams
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS
from app.models.users import User
from app.lib.file_serving import validate_file_request, validate_file_update_request


async def get_upload_or_404(id: int) -> Upload:
    """Fetch an upload by ID, raising HTTP 404 if not found."""
    upload = await Upload.get_or_none(id=id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload


async def get_upload_with_relations_or_404(id: int) -> Upload:
    """Fetch an upload with all relations by ID, raising HTTP 404 if not found."""
    upload = await Upload.get_with_relations(id=id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found")
    return upload


async def get_upload_or_404_for_read(id: int, user: User | None = None) -> Upload:
    """Fetch an upload and validate read access, raising HTTP 404 or 403 as appropriate."""
    upload = await get_upload_or_404(id)
    validate_file_request(upload, user)
    return upload


async def get_upload_or_404_for_update(id: int, user: User | None = None) -> Upload:
    """Fetch an upload and validate update access, raising HTTP 404 or 403 as appropriate."""
    upload = await get_upload_or_404(id)
    validate_file_update_request(upload, user)
    return upload


# If user is logged, include their private uploads
# TODO: Make this a user configurable option
def _build_default_readable_filter(user: Optional[User] = None, relation_prefix: str = "") -> Q:
    private_field = f"{relation_prefix}private"
    public_filter = Q(**cast(Any, {private_field: False}))

    if user:
        user_field = f"{relation_prefix}user"
        return public_filter | Q(**cast(Any, {user_field: user}))

    return public_filter


def default_readable_query_filter(user: Optional[User] = None) -> Q:
    return _build_default_readable_filter(user=user)


def default_readable_upload_tag_filter(user: Optional[User] = None) -> Q:
    """Filter tags to those with at least one readable upload."""
    return _build_default_readable_filter(user=user, relation_prefix="uploads__")


def readable_upload_queryset(
    user: Optional[User] = None,
    context_filter: Q | None = None,
    pagination: PaginationParams | None = None,
) -> QuerySet[Upload]:
    """Base queryset for all readable uploads, optionally scoped to a context."""
    qs = Upload.filter(default_readable_query_filter(user))
    if context_filter:
        qs = qs.filter(context_filter)
    if pagination:
        p = pagination.page_data()
        order = f"-{p['sort_by']}" if p['sort_order'] == 'desc' else p['sort_by']
        qs = qs.offset((p['page'] - 1) * p['page_size']).limit(p['page_size']).order_by(order)
    return qs


def writable_upload_queryset(
    user: User,
    context_filter: Q | None = None,
    pagination: PaginationParams | None = None,
) -> QuerySet[Upload]:
    """Base queryset for uploads owned by user, optionally scoped to a context."""
    return readable_upload_queryset(user, context_filter, pagination).filter(user=user)


def build_readable_upload_queryset(
    user: User,
    selected_ids: list[int],
    super_selected: bool = False,
    deselected_ids: list[int] = [],
    context_filter: Q | None = None,
) -> QuerySet[Upload]:
    """Selection-aware readable upload queryset."""
    qs = readable_upload_queryset(user, context_filter)
    if super_selected:
        return qs.filter(id__not_in=deselected_ids)
    else:
        return qs.filter(id__in=selected_ids)


async def get_readable_selected_upload_models(user: User,
    selected_ids: list[int],
    super_selected: bool = False,
    deselected_ids: list[int] = [],
    context_filter: Q | None = None,
) -> list[Upload]:
    """Get raw Upload model instances for selected uploads readable by user."""
    return await build_readable_upload_queryset(user, selected_ids, super_selected, deselected_ids, context_filter)


async def get_readable_selected_uploads(user: User, selected_ids: list[int], super_selected: bool = False, deselected_ids: list[int] = []) -> list[UploadSerializer]:
    """Get serialized selected uploads readable by user."""
    queryset = build_readable_upload_queryset(user, selected_ids, super_selected, deselected_ids) \
        .prefetch_related(*UPLOAD_PREFETCH_MODELS)
    return await UploadSerializer.from_queryset(queryset, context={"user": user})


def build_writable_upload_queryset(
    user: User,
    selected_ids: list[int],
    super_selected: bool = False,
    deselected_ids: list[int] = [],
    context_filter: Q | None = None,
) -> QuerySet[Upload]:
    """Selection-aware writable upload queryset."""
    qs = writable_upload_queryset(user, context_filter)
    if super_selected:
        return qs.filter(id__not_in=deselected_ids)
    else:
        return qs.filter(id__in=selected_ids)


async def get_writable_selected_upload_models(user: User,
    selected_ids: list[int],
    super_selected: bool = False,
    deselected_ids: list[int] = [],
    context_filter: Q | None = None,
) -> list[Upload]:
    """Get raw Upload model instances for selected uploads owned by user."""
    return await build_writable_upload_queryset(user, selected_ids, super_selected, deselected_ids, context_filter)


async def get_writable_selected_uploads(
    user: User,
    selected_ids: list[int],
    context_filter: Q | None = None,
    super_selected: bool = False,
    deselected_ids: list[int] = [],
) -> list[UploadSerializer]:
    """Get serialized selected uploads owned by user."""
    queryset = build_writable_upload_queryset(
        user=user,
        selected_ids=selected_ids,
        super_selected=super_selected,
        deselected_ids=deselected_ids,
        context_filter=context_filter,
    ).prefetch_related(*UPLOAD_PREFETCH_MODELS)

    return await UploadSerializer.from_queryset(queryset, context={"user": user})
