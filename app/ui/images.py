from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse

from app.lib.file_serving import validate_file_update_request

from app.ui.common.security import get_current_user
from app.ui.common.session import flash_message

from app.models.uploads import Upload
from app.models.users import User

from app.ui.common.errors import error_response_for_get
from app.ui.uploads import view_upload_page


router = APIRouter(prefix="/images", tags=["images"])


@router.post("/{id}/rotate/{angle}", response_class=HTMLResponse)
async def post_rotate_image(
    request: Request,
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    angle: int,
) -> Response:
    """API endpoint to rotate an image by a specified angle."""

    if angle not in [90, 180, 270]:
        return error_response_for_get(
            error_title="Invalid Rotation Angle",
            error_message="Rotation angle must be one of the following: 90, 180, 270 degrees.",
            status_code=400,
            request=request,
        )

    upload = await Upload.get_or_none(id=id).prefetch_related("user", "images")
    if upload is None:
        return error_response_for_get(
            error_title="File Not Found",
            error_message="The requested file does not exist.",
            status_code=404,
            request=request,
        )

    # Validate user access to this file
    validate_file_update_request(upload, user=current_user)

    # Rotate the image
    await upload.rotate_image(angle)

    # Return new instance of view page
    flash_message(request, f"Image rotated {angle} degrees successfully.")
    return await view_upload_page(
        request=request,
        id=upload.id,
        filename=upload.filename,
        current_user=current_user,
    )
