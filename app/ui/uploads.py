import html

from typing import Annotated
from tortoise.exceptions import ValidationError
from fastapi import APIRouter, Request, Depends, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.lib.config import get_app_config
from app.lib.error_handling import NotAuthorisedError, parse_tortoise_validation_errors
from app.lib.upload_handler import handle_uploaded_files
from app.lib.file_serving import serve_file, validate_file_request

from app.models.uploads import Upload, UploadSerializer
from app.models.users import User

from app.ui.common.errors import error_response_for_get, error_template_response
from app.ui.common.templating import templates
from app.ui.common.uploads import get_upload_or_404_for_read, get_upload_or_404_for_update, get_upload_with_relations_or_404
from app.ui.common.security import get_current_user, get_current_authenticated_user, get_or_create_authenticated_user
from app.ui.common.session import flash_message, get_client_dimensions, BREAKPOINT_FRAME_PADDING, BREAKPOINT_SIDEBAR_WIDTHS


config = get_app_config()
router = APIRouter(tags=["uploads"])


async def _render_upload_component(request: Request, current_user: User, upload_model: Upload, template: str, context: dict | None = None, status_code=200) -> Response:
    await upload_model.fetch_relations()
    upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})
    filtered_collections = upload.filtered_collections

    # Extend default context if specified
    if context is None:
        context = dict()

    # Add default context variables
    context.update({"current_user": current_user, "upload": upload, "filtered_collections": filtered_collections})

    return templates.TemplateResponse(
        request,
        template,
        context=context,
        status_code=status_code,
    )


@router.get("/upload", response_class=RedirectResponse, include_in_schema=False)
async def redirect_upload_get():
    """Redirect singular /upload route to /uploads."""
    return RedirectResponse(url="/uploads", status_code=301)


@router.get("/uploads", response_class=HTMLResponse)
async def show_upload_page_get(
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


@router.post("/uploads", response_class=HTMLResponse)
async def create_upload_post(
    current_user: Annotated[User, Depends(get_or_create_authenticated_user)],
    request: Request,
    upload_files: list[UploadFile]
) -> Response:
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
async def get_upload_without_filename_get(
    id: int,
) -> Response:
    """Redirect to an SEO friendly GET URL if filename is omitted"""

    upload = await Upload.get_or_none(id=id)
    if upload is None:
        return HTMLResponse(status_code=404)

    response = RedirectResponse(url=upload.url, status_code=301)

    return response


@router.get("/get/{id}/{filename}", response_class=Response)
async def get_upload_get(
    id: int,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    download: bool | None = False,
) -> Response:
    """Get an uploaded file."""

    upload = await Upload.get_or_none(id=id)
    if upload is None:
        return await error_response_for_get(
            error_title="Error 404: File not found",
            error_message=f"The requested file, {filename} could not be found on this server.",
            filename=filename,
            status_code=404,
        )

    return await serve_file(
        upload=upload,
        filename=filename,
        user=current_user,
        download=download
    )


@router.get("/download/{id}/{filename}", response_class=Response)
async def download_upload_get(
    id: int,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """Download an uploaded file."""

    return await get_upload_get(id=id, filename=filename, current_user=current_user, download=True)


@router.get("/view/{id}", response_class=Response)
async def view_upload_page_without_filename_get(
    id: int,
) -> Response:
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
    validate_file_request(upload)

    response = RedirectResponse(url=upload.view_url, status_code=301)

    return response


@router.get("/view/{id}/{filename}", response_class=HTMLResponse)
async def view_upload_page_get(
    request: Request,
    id: int,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
    modal_width: int | None = None,
) -> Response:
    """View an uploaded file."""

    is_modal = (
        request.headers.get("HX-Target") == "body"
        or request.query_params.get("modal", "").lower() in {"1", "true", "yes"}
    )

    # Get upload from database
    upload_model = await Upload.get_with_relations(id=id)
    if upload_model is None:
        if is_modal:
            return templates.TemplateResponse(
                request, "components/core/messages.html.j2",
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
        validate_file_request(upload_model, current_user)

    # Serialize upload for template
    upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})

    # Template context
    context = {
        "current_user": current_user,
        "upload": upload,
        "filtered_collections": upload.filtered_collections,
    }

    # Define placeholder image dimensions if we have client dimensions
    client_dimensions = get_client_dimensions(request)
    if client_dimensions is not None:
        client_breakpoint = client_dimensions.get("breakpoint", None)
        client_breakpoint_width = client_dimensions.get("breakpoint_width", None)
        if client_breakpoint_width == 0: # xs breakpoint has variable size and a minimum of 0, so use actual client size
            client_breakpoint_width = client_dimensions.get("width", None)

        if upload.image and upload.image.aspect_ratio and client_breakpoint and client_breakpoint_width:
            placeholder_image_width = (client_breakpoint_width - BREAKPOINT_FRAME_PADDING.get(str(client_breakpoint), 32)) - BREAKPOINT_SIDEBAR_WIDTHS.get(str(client_breakpoint), 0)
            placeholder_image_height = int(placeholder_image_width * upload.image.aspect_ratio)

            context["placeholder_image_width"] = placeholder_image_width
            context["placeholder_image_height"] = placeholder_image_height

    # Return page response
    if is_modal:
        context["modal_image_width"] = int(modal_width or 1920)
        return templates.TemplateResponse(request, "uploads/view-modal.html.j2", context=context)
    else:
        return templates.TemplateResponse(request, "uploads/view.html.j2", context=context)


@router.get("/uploads/{id}/image", response_class=Response)
async def get_upload_image_src_get(
    request: Request,
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
    width: int | None = None,
    height: int | None = None,
    context: str = "frame",
) -> Response:
    """Get the image source URL for an upload, with optional resizing parameters."""

    upload_model = await get_upload_or_404_for_read(id, current_user)
    await upload_model.fetch_relations()
    upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})

    if context == "modal":
        element_id = "view-modal-image"
        container_js = "window"
        ignore_height_js = "false"
        img_class = "rounded-none sm:rounded-md max-h-[calc(100dvh-1rem)] sm:max-h-[calc(100dvh-2rem)]"
        placeholder_container = "window"
        placeholder_ignore_height = False
    else:
        element_id = "view-frame-image"
        container_js = "document.querySelector('main').querySelector('article')"
        ignore_height_js = "true"
        img_class = ""
        placeholder_container = "document.querySelector('main').querySelector('article')"
        placeholder_ignore_height = True

    response = templates.TemplateResponse(
        request,
        "components/core/image-element.html.j2",
        context={
            "upload": upload,
            "width": width,
            "height": height,
            "element_id": element_id,
            "container_js": container_js,
            "ignore_height_js": ignore_height_js,
            "img_class": img_class,
            "image_context": context,
            "placeholder_container": placeholder_container,
            "placeholder_ignore_height": placeholder_ignore_height,
        },
    )

    return response

@router.delete("/uploads/{id}", response_class=Response)
async def delete_upload_delete(
    id: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    request: Request,
) -> Response:
    """Delete an uploaded file."""

    upload = await Upload.get_or_none(id=id).prefetch_related("user")
    if upload is None:
        return await error_response_for_get(
            error_title="Error 404: File not found",
            error_message="The file you are trying to delete does not exist.",
            filename="",
            status_code=404,
            request=request,
        )

    # Validate user access to this file
    if not upload.is_owner(current_user):
        raise NotAuthorisedError("You do not have permission to delete this file.")

    # Delete the file
    await upload.delete()

    # Redirect to homepage with success message
    flash_message(request, "Upload deleted successfully.")
    return Response(status_code=204, headers={"HX-Redirect": "/profile"})


@router.patch("/uploads/{id}/private", response_class=Response)
async def toggle_upload_private_patch(
        request: Request,
        id: int,
        current_user: Annotated[User, Depends(get_current_authenticated_user)],
        upload_private: Annotated[bool, Form()] = False,
) -> Response:
    """Update the private status of an upload."""
    
    upload_model = await get_upload_or_404_for_update(id, current_user)

    upload_model.private = upload_private
    await upload_model.save()

    return await _render_upload_component(request, current_user, upload_model, "components/uploads/sidebar-content.html.j2")


@router.patch("/uploads/{id}/description", response_class=Response)
async def toggle_upload_description_patch(
        request: Request,
        id: int,
        current_user: Annotated[User, Depends(get_current_authenticated_user)],
        description: Annotated[str, Form()] = '',
) -> Response:
    """Update the description of an upload."""

    upload_model = await get_upload_or_404_for_update(id, current_user)

    validation_errors = {}
    try:
        upload_model.description = html.escape(description).strip()
        await upload_model.save()
    except ValidationError as e:
        validation_errors = parse_tortoise_validation_errors(e)

    return await _render_upload_component(
        request,
        current_user,
        upload_model,
        "components/uploads/description.html.j2",
        context={"validation_errors": validation_errors},
        status_code=400 if validation_errors else 200,
    )
