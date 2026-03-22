from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse

from app.lib.file_serving import validate_file_update_request

from app.models.uploads import Upload, UploadSerializer
from app.models.users import User

from app.ui.common.security import get_current_authenticated_user
from app.ui.common.session import flash_message
from app.ui.common.errors import error_response_for_get
from app.ui.common.templating import templates
from app.ui.uploads import view_upload_page_get


router = APIRouter(prefix="/images", tags=["images"])


@router.post("/{id}/rotate/{angle}", response_class=HTMLResponse)
async def post_rotate_image(
    request: Request,
    id: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    angle: int,
) -> Response:
    """API endpoint to rotate an image by a specified angle."""

    if angle not in [90, 180, 270]:
        return await error_response_for_get(
            error_title="Invalid Rotation Angle",
            error_message="Rotation angle must be one of the following: 90, 180, 270 degrees.",
            status_code=400,
            request=request,
        )

    upload_model = await Upload.get_with_relations(id=id)
    if upload_model is None:
        return await error_response_for_get(
            error_title="File Not Found",
            error_message="The requested file does not exist.",
            status_code=404,
            request=request,
        )

    # Validate user access to this file
    validate_file_update_request(upload_model, user=current_user)

    # Rotate the image
    await upload_model.rotate_image(angle)
    flash_message(request, f"Image rotated {angle} degrees successfully.")

    # Serialise upload model
    upload = await UploadSerializer.from_tortoise_orm(upload_model)
    
    # Return rendered template depending on the HX-Target in the Request
    hx_target: str | None = request.headers.get('hx-target', None)
    context = {
        "current_user": current_user,
        "upload": upload,
    }

    # If hx-target is a gallery card
    if hx_target is not None and hx_target.startswith('gallery-card-'):
        response = templates.TemplateResponse(
            request=request,
            name="components/gallery/card.html.j2",
            context=context,
        )
        return response

    # Fallback to an upload view-frame
    response = await view_upload_page_get(
        request=request,
        id=upload.id,
        filename=upload.filename,
        current_user=current_user,
    )

    return response
