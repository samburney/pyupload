from typing import Annotated
from fastapi import APIRouter, Request, Depends, UploadFile
from fastapi.responses import HTMLResponse

from app.lib.config import get_app_config
from app.lib.upload_handler import handle_uploaded_files

from app.models.users import User

from app.ui.common import templates
from app.ui.common.security import get_or_create_authenticated_user


config = get_app_config()
router = APIRouter(tags=["uploads"])


@router.get("/upload", response_class=HTMLResponse)
async def show_upload_page(
    request: Request
):
    """Render the upload page."""
    return templates.TemplateResponse(request, "uploads/index.html.j2")


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

