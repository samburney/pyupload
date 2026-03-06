from fastapi import HTTPException

from app.models.uploads import Upload
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
