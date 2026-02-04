from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request

from app.lib.config import get_app_config
from app.api.auth import get_current_user

from app.models import Upload, Upload_Pydantic, User


config = get_app_config()
router = APIRouter(prefix="/files", tags=["files"])


@router.get("/{id}")
async def get_file(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """API endpoint providing file metadata."""
    
    upload = await Upload.get_or_none(id=id).prefetch_related("user", "images")

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
    upload_data["get_url"] = upload.url
    upload_data["view_url"] = upload.view_url
    upload_data["download_url"] = upload.download_url

    # Update field names where sensible
    upload_data['name'] = upload_data['originalname']
    upload_data["originalname"] = upload_data['originalname'] + upload.dot_ext

    # Add image data if applicable
    image_data = upload_data.pop("images")
    if upload.is_image:
        upload_data["image"] = image_data
    
    return upload_data
