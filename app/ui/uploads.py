from typing import Annotated
from fastapi import APIRouter, Request, Depends, UploadFile
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.lib.config import get_app_config, logger
from app.lib.error_handling import NotAuthorisedError
from app.ui.common.errors import error_response_for_get
from app.lib.upload_handler import handle_uploaded_files
from app.lib.file_serving import serve_file, validate_file_request

from app.models.uploads import Upload, UploadSerializer
from app.models.users import User

from app.ui.common.templating import templates
from app.ui.common.security import get_current_user, get_or_create_authenticated_user


config = get_app_config()
router = APIRouter(tags=["uploads"])


@router.get("/upload", response_class=HTMLResponse)
async def show_upload_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Render the upload page."""

    return templates.TemplateResponse(
        request,
        "uploads/index.html.j2",
        context={
            "current_user": current_user,
        },
    )


@router.post("/upload", response_class=HTMLResponse)
async def create_upload(
    current_user: Annotated[User, Depends(get_or_create_authenticated_user)],
    request: Request,
    upload_files: list[UploadFile]
):
    """Handle multiple uploaded files."""

    # Handle file uploads
    error_messages = []
    info_messages = []

    results = await handle_uploaded_files(user=current_user, files=upload_files)
    uploaded_files = []
    for result in results:
        if result.status == "success" and result.metadata is not None:
            info_messages.append(f"File '{result.metadata.filename}' uploaded successfully.")
            uploaded_files.append(result)
        else:
            error_messages.append(f'{result.message}' if result.message else "An unknown error occurred during file upload.")

    # Render response
    response = templates.TemplateResponse(
        request=request,
        name="uploads/list.html.j2",
        context={
            "current_user": current_user,
            "info_messages": info_messages,
            "error_messages": error_messages,
            "uploaded_files": uploaded_files,
        },
    )

    return response


@router.get("/get/{id}", response_class=Response)
async def get_upload_without_filename(
    id: int,
):
    """Redirect to an SEO friendly GET URL if filename is omitted"""

    upload = await Upload.get_or_none(id=id)
    if upload is None:
        return HTMLResponse(status_code=404)

    response = RedirectResponse(url=upload.url, status_code=301)

    return response


@router.get("/get/{id}/{filename}", response_class=Response)
async def get_upload(
    id: int,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    download: bool | None = False,
):
    """Get an uploaded file."""

    upload = await Upload.get_or_none(id=id)
    if upload is None:
        return error_response_for_get(
            error_title="Error 404: File not found",
            error_message=f"The requested file, {filename} could not be found on this server.",
            filename=filename,
            status_code=404,
        )

    try:
        return await serve_file(
            upload=upload,
            filename=filename,
            user=current_user,
            download=download
        )
    except Exception as e:
        logger.error(f"Unexpected error serving file {id}/{filename}: {e}", exc_info=True)
        return HTMLResponse(status_code=500)


@router.get("/download/{id}/{filename}", response_class=Response)
async def download_upload(
    id: int,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
):
    """Download an uploaded file."""

    return await get_upload(id=id, filename=filename, current_user=current_user, download=True)


@router.get("/view/{id}", response_class=Response)
async def view_upload_without_filename(
    id: int,
):
    """Redirect to an SEO friendly GET URL if filename is omitted"""

    upload = await Upload.get_or_none(id=id)
    if upload is None:
        return HTMLResponse(status_code=404)

    # Validate the file request before redirecting.  We're not validating the
    # user here, so private files will fail to redirect to prevent information
    # disclosure about the existence of private files to unauthenticated users.
    # This will break private files for users who are logged in and are trying
    # to access their own private files without the filename in the URL, but
    # given this is a helper mostly for SEO anyway, it's a reasonable tradeoff.
    try:
        validate_file_request(upload)
    except NotAuthorisedError as e:
        return error_response_for_get(
            error_title="Error 403: Unauthorized",
            error_message=f"An error occurred processing your request: {e}",
            filename=None,
            status_code=403,
            as_html=True,
        )
    except FileNotFoundError as e:
        return error_response_for_get(
            error_title="Error 404: File not found",
            error_message=f"An error occurred processing your request: {e}",
            filename=None,
            status_code=404,
            as_html=True,
        )

    response = RedirectResponse(url=upload.view_url, status_code=301)

    return response


@router.get("/view/{id}/{filename}", response_class=HTMLResponse)
async def view_upload(
    request: Request,
    id: int,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    modal: bool | None = False,
):
    """View an uploaded file."""

    # Get upload from database
    upload_model = await Upload.get_or_none(id=id).prefetch_related("user", "images")
    if upload_model is None:
        if modal:
            return templates.TemplateResponse(
                request, "layout/messages.html.j2",
                status_code=404,
                context={"error_messages": ["Upload not found"]},
            )
        else:
            return templates.TemplateResponse(
                request, "layout/error.html.j2",
                status_code=404,
                context={"error_messages": ["Upload not found"]},
            )
    else:
        try:
            validate_file_request(upload_model, current_user)
        except NotAuthorisedError as e:
            return error_response_for_get(
                error_title="Error 403: Unauthorized",
                error_message=f"An error occurred processing your request for {filename}: {e}",
                filename=filename,
                status_code=403,
                as_html=True,
                request=request,
            )
        except FileNotFoundError as e:
            return error_response_for_get(
                error_title="Error 404: File not found",
                error_message=f"An error occurred processing your request for {filename}: {e}",
                filename=filename,
                status_code=404,
                as_html=True,
                request=request,
            )

    # Serialize upload for template
    upload = await UploadSerializer.from_tortoise_orm(upload_model)

    # Template context
    context = {
        "current_user": current_user,
        "upload": upload,
    }

    if modal:
        return templates.TemplateResponse(request, "uploads/view-modal.html.j2", context=context)
    else:
        return templates.TemplateResponse(request, "uploads/view.html.j2", context=context)
