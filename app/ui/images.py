import asyncio
import json

from typing import Annotated
from fastapi import APIRouter, Depends, Request, Response, Form
from fastapi.responses import HTMLResponse

from app.lib.config import logger
from app.models.uploads import UploadSerializer
from app.models.users import User

from app.ui.common.security import get_current_authenticated_user
from app.ui.common.session import flash_message
from app.ui.common.responses import error_template_response
from app.ui.common.uploads import build_writable_upload_queryset

from app.ui.uploads import view_upload_page_get


router = APIRouter(prefix="/images", tags=["images"])


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
        return await error_template_response(
            request=request,
            title="Invalid Rotation Angle",
            error_messages=["Rotation angle must be one of the following: 90, 180, 270 degrees."],
            status_code=400,
        )

    upload_qs = build_writable_upload_queryset(
        user=current_user,
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

    flash_message(request, f"{len(image_models)} image{'s' if len(image_models) != 1 else ''} rotated {angle} degrees successfully.")

    if request.headers.get('hx-target') == 'view-frame-image':
        upload_model = image_models[0]
        upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})
        return await view_upload_page_get(
            request=request,
            id=upload.id,
            filename=upload.filename,
            current_user=current_user,
        )

    # Gallery: HX-Location in-place refresh
    redirect_url = request.headers.get('referer', None)
    if not redirect_url:
        redirect_url = request.url_for('index_get')

    hx_location = json.dumps({
        "source": request.headers.get('hx-trigger'),
        "path": str(redirect_url),
        "target": "#gallery-grid",
        "select": "#gallery-grid > *, #messages",
    })

    return Response(status_code=204, headers={"HX-Location": hx_location})
