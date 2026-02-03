from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request

from app.lib.config import get_app_config
from app.api.auth import get_current_user

from app.models import Upload, Upload_Pydantic, User


config = get_app_config()
router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{id}")
async def get_file(
    request: Request,
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """API endpoint providing file metadata."""
    
    upload = await Upload.get_or_none(id=id).prefetch_related("user")

    # Check file exists
    if not upload:
        raise HTTPException(status_code=404, detail="File not found")

    # Check user has permissions on this file
    if not upload.is_owner(current_user) and upload.is_private:
        raise HTTPException(status_code=403, detail="You do not have permission to access this file")

    # Enrich data coming from model
    upload_pydantic = await Upload_Pydantic.from_tortoise_orm(upload)
    upload_data = upload_pydantic.model_dump()
    
    # Add additional fields
    upload_data["is_image"] = upload.is_image
    upload_data["is_private"] = upload.is_private
    upload_data["is_owner"] = upload.is_owner(current_user)
    url_base = f"{request.url.scheme}://{request.url.hostname}{':' + str(request.url.port) if request.url.port not in [80, 443] else ''}"
    upload_data["get_url"] = f"{url_base}{upload.url}"
    upload_data["view_url"] = f"{url_base}{upload.view_url}"
    upload_data["download_url"] = f"{url_base}{upload.download_url}"

    # Update field names where sensible
    image_data = upload_data.pop("images")
    if upload.is_image:
        upload_data["image"] = image_data
    
    return upload_data
