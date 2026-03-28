from fastapi import HTTPException

from tortoise.queryset import QuerySet

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


def build_writable_upload_queryset(current_user: User, selected_ids: list[int], super_selected: bool = False, deselected_ids: list[int] = []) -> QuerySet[Upload]:
    """Build a queryset for uploads owned by current_user, respecting super-select mode."""
    if super_selected:
        return Upload.filter(user=current_user, id__not_in=deselected_ids)
    else:
        return Upload.filter(user=current_user, id__in=selected_ids)


async def get_writable_selected_upload_models(current_user: User, selected_ids: list[int], super_selected: bool = False, deselected_ids: list[int] = []) -> list[Upload]:
    """Get raw Upload model instances for selected uploads owned by current_user."""
    return await build_writable_upload_queryset(current_user, selected_ids, super_selected, deselected_ids)


async def get_writable_selected_uploads(current_user: User, selected_ids: list[int], super_selected: bool = False, deselected_ids: list[int] = []) -> list[UploadSerializer]:
    """Get serialized selected uploads owned by current_user."""
    queryset = build_writable_upload_queryset(current_user, selected_ids, super_selected, deselected_ids) \
        .prefetch_related(*UPLOAD_PREFETCH_MODELS)
    return await UploadSerializer.from_queryset(queryset, context={"user": current_user})
