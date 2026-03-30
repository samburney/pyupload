from datetime import datetime, timedelta, timezone
from typing import Annotated, Optional

from fastapi import APIRouter, Depends, Form, Request, Response
from fastapi.responses import FileResponse, HTMLResponse
from fastapi.exceptions import HTTPException

from app.models.uploads import Upload
from app.models.users import User
from app.models.download_archives import (
    DownloadArchive,
    DownloadArchiveSerializer,
    DOWNLOAD_ARCHIVE_PREFETCH_MODELS,
    ArchiveFormatsEnum,
    ArchiveStatusEnum
)

from app.lib.config import get_app_config
from app.lib.helpers import make_unique_filename, clean_text, sanitise_filename
from app.lib.scheduler import schedule_archive_job

from app.ui.common.security import get_current_authenticated_user
from app.ui.common.session import flash_message
from app.ui.common.templating import templates
from app.ui.common.uploads import get_readable_selected_upload_models


config = get_app_config()
router = APIRouter(prefix="/archives", tags=["download_archives"])


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
    upload_ids = sorted(upload.id for upload in upload_models)
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


@router.get("/profile-list", response_class=HTMLResponse)
async def profile_archive_list_get(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
) -> HTMLResponse:
    """Render user profile download archives table"""

    # If this isn't a HTMX request, bail out now
    if not request.headers.get('hx-request', False):
        raise HTTPException(status_code=400, detail='Not a valid HTMX request')

    # Get list of non-expired download archives
    expiry_cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=config.archive_max_age_hours)
    download_archive_models = DownloadArchive.filter(user=current_user, created_at__gte=expiry_cutoff).order_by('-created_at').prefetch_related(*DOWNLOAD_ARCHIVE_PREFETCH_MODELS)
    download_archives = await DownloadArchiveSerializer.from_queryset(download_archive_models)

    response = templates.TemplateResponse(
        request,
        "archives/partials/profile-list.html.j2",
        {
            "current_user": current_user,
            "download_archives": download_archives,
        }
    )

    return response


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

    if download_archive_model.status == ArchiveStatusEnum.ready:
        flash_message(request, "Your download archive is ready to download.")

    # Return updated download button
    response = templates.TemplateResponse(
        request=request,
        name="components/archive/download-button.html.j2",
        context={
            "download_archive": download_archive_model,
        }
    )

    return response


@router.post("/{download_archive_id}/cancel")
async def cancel_pending_archive_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    download_archive_id: str,
) -> Response:
    """Update current download archive progress status"""

    # If this isn't a HTMX request, bail out now
    if not request.headers.get('hx-request', False):
        raise HTTPException(status_code=400, detail='Not a valid HTMX request')

    # Get DownloadArchive model
    download_archive_model = await DownloadArchive.get_or_none(id=download_archive_id,
                                                               user=current_user,
                                                               status=ArchiveStatusEnum.pending)
    if not download_archive_model:
        flash_message(request, "The requested download archive could not be found.", "error")
        response = templates.TemplateResponse(
            request=request,
            name="components/archive/download-button.html.j2",
            status_code=404,
        )
        return response

    # If cancel failed (Probably moved to 'processing' state already), do nothing
    if not await download_archive_model.cancel():
        flash_message(request, "Archive download cancel request failed.", message_type="warning")
        response = Response(
            status_code=204,
        )

    else:
        flash_message(request, "Pending archive request cancelled.")
        response = Response(
            status_code=204,
            headers={"HX-Trigger": '{"update-sidebar": {}}'},
        )
    return response


@router.delete("/{download_archive_id}")
async def delete_archive_delete(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    download_archive_id: str,
) -> Response:
    """Delete a download archive"""

    # If this isn't a HTMX request, bail out now
    if not request.headers.get('hx-request', False):
        raise HTTPException(status_code=400, detail='Not a valid HTMX request')

    # Get DownloadArchive model
    download_archive_model = await DownloadArchive.get_or_none(id=download_archive_id,
                                                               user=current_user)

    if not download_archive_model:
        flash_message(request, "The requested download archive could not be found.", "error")
        response = templates.TemplateResponse(
            request=request,
            name="components/core/messages.html.j2",
            status_code=404,
        )
        return response

    # Save filename for future response message
    download_archive_file_name = download_archive_model.filename

    # Delete download archive
    await download_archive_model.delete()

    if download_archive_model.status in (ArchiveStatusEnum.pending, ArchiveStatusEnum.processing):
        flash_message(request, f"{download_archive_model.status.value} archive cancelled: {download_archive_file_name}")
    else:
        flash_message(request, f"Download archive successfully deleted: {download_archive_file_name}")

    current_url = request.headers.get('hx-current-url', None)
    if current_url and '/profile' in current_url:
        response = templates.TemplateResponse(
            request=request,
            name="components/core/messages.html.j2",
            status_code=200,
            headers={"HX-Trigger": '{"refresh-profile-download-archives-table": {}}'},
        )
    else:
        response = Response(
            status_code=204,
        )
    return response


@router.get("/{download_archive_id}/download/{download_archive_filename}")
@router.get("/{download_archive_id}/download")
async def download_archive_get(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    download_archive_id: str,
    download_archive_filename: Optional[str] = None,
) -> Response:
    """Return FileResponse of prepared DownloadArchive file for user to download"""

    # Get DownloadArchive model
    download_archive_model = await DownloadArchive.get_or_none(id=download_archive_id, user=current_user)
    if not download_archive_model:
        flash_message(request, "The requested download archive could not be found.", "error")
        response = templates.TemplateResponse(
            request=request,
            name="layout/error.html.j2",
            status_code=404,
        )
        return response
    
    # Check archive status
    if download_archive_model.status != ArchiveStatusEnum.ready:
        if download_archive_model.status == ArchiveStatusEnum.pending or download_archive_model.status == ArchiveStatusEnum.processing:
            flash_message(request, f"The requested download archive is still {download_archive_model.status.value}, please try again later.", "warning")
        elif download_archive_model.status == ArchiveStatusEnum.failed:
            flash_message(request, f"Creation of the requested download archive {download_archive_model.status.value}.", "error")
        response = templates.TemplateResponse(
            request=request,
            name="layout/error.html.j2",
            status_code=404,
        )
        return response

    # Determine filename
    if not download_archive_filename:
        download_archive_filename = download_archive_model.filename
    filename = sanitise_filename(download_archive_filename) or sanitise_filename(download_archive_model.filename) or download_archive_model.filename

    # Determine and validate file_path
    file_path = download_archive_model.file_path
    if not file_path.exists() or not file_path.is_file():
        flash_message(request, "The requested download archive could not be found.", "error")
        response = templates.TemplateResponse(
            request=request,
            name="layout/error.html.j2",
            status_code=404,
        )
        return response
    
    # Determine media_type
    media_type = download_archive_model.format.mimetype

    # Return file response
    response = FileResponse(file_path, media_type=media_type)

    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    response.headers["Cache-Control"] = "private, max-age=86400"
    
    return response
