from typing import Annotated
from fastapi import APIRouter, Depends, HTTPException, Request

from app.lib.config import get_app_config
from app.lib.file_serving import validate_file_update_request

from app.api.auth import get_current_user

from app.models.uploads import Upload, UploadSerializer
from app.models.users import User


config = get_app_config()
router = APIRouter(prefix="/images", tags=["images"])


@router.post("/{id}/rotate")
async def post_rotate_image(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    angle: int,
):
    """API endpoint to rotate an image by a specified angle."""

    if angle not in [90, 180, 270]:
        raise HTTPException(status_code=400, detail="Invalid rotation angle. Must be one of: 90, 180, 270.")

    upload = await Upload.get_with_relations(id=id)
    if upload is None:
        raise HTTPException(status_code=404, detail="Image not found.")

    # Validate user access to this file
    validate_file_update_request(upload, user=current_user)

    # Rotate the image
    await upload.rotate_image(angle)

    # Get new instance of upload to ensure we have the latest metadata after rotation
    new_upload_data = await UploadSerializer.from_tortoise_orm(upload)

    return new_upload_data
