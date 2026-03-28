from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.exceptions import HTTPException

from app.models.uploads import Upload
from app.models.users import User
from app.models.download_archives import DownloadArchive, ArchiveFormatsEnum

from app.lib.helpers import make_unique_filename, clean_text
from app.lib.scheduler import schedule_archive_job

from app.ui.common.security import get_current_authenticated_user
from app.ui.common.session import flash_message
from app.ui.common.templating import templates
from app.ui.common.uploads import get_readable_selected_upload_models


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


@router.post('/request/{download_format}', response_class=Response)
async def request_uploads_archive_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    download_format: str,
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Request download archive of selected files"""

    # If this isn't a HTMX request, bail out now
    if not request.headers.get('hx-request', False):
        raise HTTPException(status_code=400, detail='Not a valid HTMX request')

    # Validate requested format
    try:
        archive_format = ArchiveFormatsEnum(download_format)
    except ValueError:
        flash_message(request, f"An invalid archive format was requested: {download_format}", "error")
        return templates.TemplateResponse(request, 'components/core/messages.html.j2', status_code=400)

    # Filter selected uploads to only those readable by the current_user
    upload_models: list[Upload] = await get_readable_selected_upload_models(current_user, selected_ids, super_selected, deselected_ids)
    if not upload_models:
        flash_message(request, "You do not have permission to download any of the selected uploads.", "error")
        return templates.TemplateResponse(request, 'components/core/messages.html.j2', status_code=403)

    # Create new DownloadArchive model
    upload_ids = [upload.id for upload in upload_models]
    clean_username = clean_text(current_user.username)
    unique_filename = make_unique_filename(f"archive_{clean_username}")
    archive_filename = f"{unique_filename}.{archive_format.value}"

    download_archive_data = {
        "user": current_user,
        "upload_ids": upload_ids,
        "filename": archive_filename,
        "format": archive_format,
    }
    download_archive_model = await DownloadArchive.create(**download_archive_data)

    # Add archive creating to scheduler queue
    schedule_archive_job(download_archive_model.id)

    # Return new download button
    flash_message(request, "Download archive creation has been queued.")
    response = templates.TemplateResponse(
        request=request,
        name="components/archive/download-button.html.j2",
        context={
            "download_archive": download_archive_model,
        }
    )

    return response
