import asyncio
import json

from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response, Form
from fastapi.responses import HTMLResponse

from app.lib.config import logger
from app.lib.file_serving import validate_file_update_request

from app.models.uploads import Upload, UploadSerializer
from app.models.users import User

from app.ui.common.security import get_current_authenticated_user
from app.ui.common.session import flash_message
from app.ui.common.errors import error_response_for_get, error_template_response
from app.ui.common.templating import templates
from app.ui.common.uploads import build_writable_upload_queryset

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


@router.post("/rotate", response_class=HTMLResponse)
async def rotate_selected_images_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    angle: Annotated[int, Form()],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """API endpoint to rotate an image by a specified angle."""

    if angle not in [90, 180, 270]:
        return await error_response_for_get(
            error_title="Invalid Rotation Angle",
            error_message="Rotation angle must be one of the following: 90, 180, 270 degrees.",
            status_code=400,
            request=request,
        )

    upload_qs = build_writable_upload_queryset(
        current_user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )
    upload_models = await upload_qs.prefetch_related("images")
    image_models = [u for u in upload_models if u.is_image]

    if not image_models:
        return await error_template_response(request, ["No images are selected."], 404, "File(s) not found")

    try:
        await asyncio.gather(*[i.rotate_image(angle) for i in image_models])
    except Exception as e:
        logger.exception("Failed to rotate uploads: %s", e)
        return await error_template_response(
            request=request,
            title="An error occurred rotating images",
            error_messages=[str(e)],
            status_code=500,
        )

    # Determine redirect URL
    redirect_url = request.headers.get('referer', None)
    if not redirect_url:
        redirect_url = request.url_for('index_get')

    hx_location_dict: dict = {
        "source": request.headers.get('hx-trigger'),
        "path": redirect_url,
        "target": "#gallery-grid",
        "select": "#gallery-grid > *, #messages",
    }
    hx_location = json.dumps(hx_location_dict)

    headers = {
        "HX-Location": str(hx_location),
    }

    flash_message(request, f"{len(image_models)} images rotated {angle} degrees successfully.")
    response = Response(status_code=204, headers=headers)

    return response
