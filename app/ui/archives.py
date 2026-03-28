from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response
from fastapi.responses import HTMLResponse
from fastapi.exceptions import HTTPException

from app.models.uploads import Upload, UploadSerializer
from app.models.users import User
from app.models.download_archives import DownloadArchive

from app.ui.common.security import get_current_authenticated_user
from app.ui.common.session import flash_message
from app.ui.common.templating import templates


router = APIRouter(prefix="/archives", tags=["download_archives"])


@router.get("/{download_archive_id}/status")
async def update_archive_status_get(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    download_archive_id: str,
) -> Response:
    """Update current download archive progress status"""

    # If this isn't a HTMX request, bail out now
    if not request.headers.get('hx-request', False):
        raise HTTPException(status_code=400, detail='Not a valid HTMX request')

    # Get DownloadArchive model
    download_archive_model = await DownloadArchive.get_or_none(id=download_archive_id, user=current_user)
    if not download_archive_model:
        flash_message(request, "The requested download archive could not be found.", "error")
        response = templates.TemplateResponse(
            request=request,
            name="components/archive/download-button.html.j2",
            status_code=404,
        )
        return response

    # Return updated download button
    response = templates.TemplateResponse(
        request=request,
        name="components/archive/download-button.html.j2",
        context={
            "download_archive": download_archive_model,
        }
    )
    
    return response
