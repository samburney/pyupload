import html

from typing import Annotated
from fastapi import APIRouter, Request, Depends, UploadFile, Form
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from app.lib.config import get_app_config
from app.lib.helpers import make_clean_tag
from app.lib.error_handling import NotAuthorisedError
from app.lib.upload_handler import handle_uploaded_files
from app.lib.file_serving import serve_file, validate_file_request

from app.models.uploads import Upload, UploadSerializer
from app.models.users import User
from app.models.tags import Tag
from app.models.collections import Collection

from app.ui.common.errors import error_response_for_get, error_template_response
from app.ui.common.templating import templates
from app.ui.common.uploads import get_upload_or_404_for_read, get_upload_or_404_for_update, get_upload_with_relations_or_404
from app.ui.common.security import get_current_user, get_current_authenticated_user, get_or_create_authenticated_user
from app.ui.common.session import flash_message


config = get_app_config()
router = APIRouter(tags=["uploads"])


async def _render_tag_input(request: Request, current_user: User, upload_model: Upload, status_code: int) -> Response:
    await upload_model.fetch_relations()
    upload = await UploadSerializer.from_tortoise_orm(upload_model)
    return templates.TemplateResponse(
        request,
        "components/tag-input.html.j2",
        context={"current_user": current_user, "upload": upload},
        status_code=status_code,
    )


async def _render_upload_component(request: Request, current_user: User, upload_model: Upload, template: str) -> Response:
    await upload_model.fetch_relations()
    upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})
    filtered_collections = await Collection.get_filtered_for_upload(upload_model, current_user)
    return templates.TemplateResponse(
        request,
        template,
        context={"current_user": current_user, "upload": upload, "filtered_collections": filtered_collections},
    )


@router.get("/upload", response_class=HTMLResponse)
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


@router.post("/upload", response_class=HTMLResponse)
async def create_upload_post(
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
async def get_upload_without_filename_get(
    id: int,
):
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
):
    """Download an uploaded file."""

    return await get_upload_get(id=id, filename=filename, current_user=current_user, download=True)


@router.get("/view/{id}", response_class=Response)
async def view_upload_page_without_filename_get(
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
    validate_file_request(upload)

    response = RedirectResponse(url=upload.view_url, status_code=301)

    return response


@router.get("/view/{id}/{filename}", response_class=HTMLResponse)
async def view_upload_page_get(
    request: Request,
    id: int,
    filename: str,
    current_user: Annotated[User, Depends(get_current_user)],
) -> Response:
    """View an uploaded file."""

    is_modal = request.headers.get("HX-Target") == "body"

    # Get upload from database
    upload_model = await Upload.get_with_relations(id=id)
    if upload_model is None:
        if is_modal:
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
        validate_file_request(upload_model, current_user)

    # Serialize upload for template
    upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})

    # Get collections with filter applied, excluding those already linked to the upload
    filtered_collections = await Collection.get_filtered_for_upload(upload_model, current_user)

    # Template context
    context = {
        "current_user": current_user,
        "upload": upload,
        "filtered_collections": filtered_collections,
    }

    if is_modal:
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
        placeholder_sidebar = False
    else:
        element_id = "view-frame-image"
        container_js = "document.querySelector('main').querySelector('article')"
        ignore_height_js = "true"
        img_class = ""
        placeholder_container = "document.querySelector('main').querySelector('article')"
        placeholder_sidebar = True

    response = templates.TemplateResponse(
        request,
        "components/image-element.html.j2",
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
            "placeholder_sidebar": placeholder_sidebar,
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
        return error_response_for_get(
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
    flash_message(request, "File deleted successfully.")
    return Response(status_code=204, headers={"HX-Redirect": "/profile"})


@router.post("/uploads/{id}/tag-suggestions", response_class=HTMLResponse)
async def get_tag_suggestions_post(
    request: Request,
    id: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    tag_name: Annotated[str, Form()] = "",
):
    """Get tag suggestions for current upload, filtered by the current input value."""

    if tag_name == '':
        return Response(status_code=204)  # Return empty response if input is empty to avoid unnecessary database query

    # Get upload from database
    upload_model = await get_upload_with_relations_or_404(id)

    # Serialize upload for template
    upload = await UploadSerializer.from_tortoise_orm(upload_model)

    # Get tag suggestions
    new_tag = None
    suggested_tags = await Tag.all().filter(name__icontains=tag_name) \
        .exclude(id__in=[tag.id for tag in upload_model.tags])[:5] \
        .values_list("name", flat=True)

    if tag_name != '':
        if tag_name not in suggested_tags:
            new_tag = make_clean_tag(tag_name)

    return templates.TemplateResponse(
        request,
        "components/tag-suggestions.html.j2",
        context={
            "upload": upload,
            "new_tag": new_tag,
            "existing_tags": suggested_tags,
        },
    )


@router.post("/uploads/{id}/tag", response_class=Response)
async def upload_add_tag_post(
    id: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    request: Request,
    tag_name: Annotated[str, Form()],
) -> Response:
    """Add a tag to an upload."""
    
    # Get upload from database
    upload_model = await get_upload_with_relations_or_404(id)

    # Add tag to the upload, creating the tag if it doesn't exist
    try:
        await Tag.add_or_create_for_upload(upload_model, tag_name)

    except ValueError as e:
        return error_template_response(request, [str(e)], status_code=400)

    return await _render_tag_input(request, current_user, upload_model, status_code=201)


@router.delete("/uploads/{id}/tag", response_class=Response)
async def upload_remove_tag_delete(
    id: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    request: Request,
    tag_name: str,
) -> Response:
    """Remove a tag from an upload."""
    
    # Get upload from database
    upload_model = await get_upload_with_relations_or_404(id)

    # Remove tag from upload
    try:
        await Tag.remove_tag_from_upload(upload_model, tag_name)

    except ValueError as e:
        return error_template_response(request, [str(e)], status_code=400)

    return await _render_tag_input(request, current_user, upload_model, status_code=200)


@router.post("/uploads/{id}/collection-search", response_class=HTMLResponse)
async def get_collection_suggestions_post(
    request: Request,
    id: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    collection_name: Annotated[str, Form()] = "",
):
    """Get collection suggestions for current upload, filtered by the current input value."""

    # Get upload from database
    upload_model = await get_upload_with_relations_or_404(id)

    # Serialize upload for template
    upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})

    # Get collections with filter applied, excluding those already linked to the upload
    filtered_collections = await Collection.get_filtered_for_upload(upload_model, current_user, name_filter=collection_name)

    return templates.TemplateResponse(
        request,
        "components/collections-combo-selector-items.html.j2",
        context={
            "upload": upload,
            "filtered_collections": filtered_collections,
        },
    )


@router.post("/uploads/{id}/collection", response_class=Response)
async def upload_add_collection_post(
    id: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    request: Request,
    collection_name: Annotated[str, Form()] = "",
) -> Response:
    """Add a collection to an upload."""
    
    # Get upload from database
    upload_model = await get_upload_with_relations_or_404(id)

    # Add collection to the upload, creating the collection if it doesn't exist
    try:
        await Collection.add_or_create_for_upload(
            upload=upload_model, collection_name=collection_name, user_id=current_user.id
        )

    except ValueError as e:
        return error_template_response(request, [str(e)], status_code=400)

    # Serialize upload for template
    await upload_model.fetch_relations()  # Refresh related models
    upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})

    # Get collections with filter applied, excluding those already linked to the upload
    filtered_collections = await Collection.get_filtered_for_upload(upload_model, current_user)

    # Build response
    response = templates.TemplateResponse(
        request,
        "components/collections-combo-selector.html.j2",
        context={
            "current_user": current_user,
            "upload": upload,
            "filtered_collections": filtered_collections,
        },
        status_code=201,
    )

    return response


@router.patch("/uploads/{id}/collection", response_class=Response)
async def update_upload_collections_patch(
    request: Request,
    id: int,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    collection_ids: Annotated[list[int], Form()] = [],
):

    """Update the collections linked to an upload based on a list of collection IDs."""
    
    error_messages = []
    collections = []

    # Confirm user owns the collections provided
    for collection_id in collection_ids:
        collection = await Collection.get_or_none(id=collection_id).prefetch_related("user")
        if collection is None or collection.user.id != current_user.id:
            error_message = f"Collection with ID {collection_id} not found or insufficient permissions."
            error_messages.append(error_message)

        else:
            collections.append(collection)

    # If no supplied collection IDs were invalid, return error response
    if error_messages and len(error_messages) == len(collection_ids):
        return templates.TemplateResponse(
            request, "layout/error.html.j2",
            status_code=400,
            context={"error_messages": error_messages},
        )

    # Add valid collections to the upload
    upload_model = await get_upload_with_relations_or_404(id)

    # Get list of user-owned collections already on the upload
    user_collection_ids = await upload_model.collections.filter(user=current_user).values_list("id", flat=True)

    # Add new collections to upload
    collections_to_add = [collection for collection in collections if collection.id not in user_collection_ids]
    if len(collections_to_add) > 0:
        await upload_model.collections.add(*collections_to_add)

    # Remove collections that are no longer included
    collection_ids_to_remove = [collection for collection in user_collection_ids if collection not in collection_ids]
    if len(collection_ids_to_remove) > 0:
        collections_to_remove = await Collection.filter(id__in=collection_ids_to_remove)
        await upload_model.collections.remove(*collections_to_remove)

    # Refresh upload collections and serialize for template
    await upload_model.fetch_relations()  # Refresh related models
    upload = await UploadSerializer.from_tortoise_orm(upload_model, context={"user": current_user})

    # Get collections with filter applied, excluding those already linked to the upload
    filtered_collections = await Collection.get_filtered_for_upload(upload_model, current_user)

    # Build response
    response = templates.TemplateResponse(
        request,
        "components/collections-combo-selector-items.html.j2",
        context={
            "current_user": current_user,
            "upload": upload,
            "filtered_collections": filtered_collections,
        },
        status_code=202,
    )

    return response


@router.patch("/uploads/{id}/private", response_class=Response)
async def toggle_upload_private_patch(
        request: Request,
        id: int,
        current_user: Annotated[User, Depends(get_current_authenticated_user)],
        upload_private: Annotated[bool, Form()] = False,
):
    """Update the private status of an upload."""
    
    upload_model = await get_upload_or_404_for_update(id, current_user)

    upload_model.private = upload_private
    await upload_model.save()

    return await _render_upload_component(request, current_user, upload_model, "components/view-sidebar.html.j2")

@router.patch("/uploads/{id}/description", response_class=Response)
async def toggle_upload_description_patch(
        request: Request,
        id: int,
        current_user: Annotated[User, Depends(get_current_authenticated_user)],
        description: Annotated[str, Form()] = '',
):
    """Update the description of an upload."""

    upload_model = await get_upload_or_404_for_update(id, current_user)

    upload_model.description = html.escape(description).strip()
    await upload_model.save()

    return await _render_upload_component(request, current_user, upload_model, "components/upload-description.html.j2")
