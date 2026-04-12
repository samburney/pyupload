import asyncio

from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response, HTMLResponse
from fastapi.exceptions import HTTPException

from app.models.collections import Collection
from app.models.users import User

from app.ui.common.errors import error_template_response
from app.ui.common.security import get_current_authenticated_user
from app.ui.common.templating import templates
from app.ui.common.uploads import (
    build_readable_upload_queryset,
)


router = APIRouter(prefix="/collections", tags=["collections"])


@router.post("/suggestions", response_class=HTMLResponse)
async def get_collection_suggestions_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    collection_search: Annotated[str, Form()] = "",
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Get collection suggestions for current upload, filtered by the current input value."""

    # Get uploads from database including related collections
    upload_qs = build_readable_upload_queryset(
        current_user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )
    upload_models = await upload_qs.prefetch_related("collections")

    # Get uploads from database
    if not len(upload_models):
        raise HTTPException(status_code=404, detail="None of the selected uploads provided exist.")

    # Get selected collections
    selected_collections = await Collection.get_combined_for_uploads(user=current_user, uploads=upload_models)

    # Get collections with filter applied, excluding those already linked to the upload
    selected_collection_ids = set(c.id for c in selected_collections)
    filtered_collections = await Collection.filter(user=current_user, name__icontains=collection_search) \
        .exclude(id__in=selected_collection_ids).limit(5).order_by("name")

    return templates.TemplateResponse(
        request,
        "components/collections/combo-selector-items.html.j2",
        context={
            "current_user": current_user,
            "selected_collections": selected_collections,
            "filtered_collections": filtered_collections,
        },
    )


@router.post("", response_class=Response)
async def upload_add_collection_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    collection_search: Annotated[str, Form()],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Add a collection to an upload."""

    # Get uploads from database including related collections
    upload_qs = build_readable_upload_queryset(
        current_user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )
    upload_models = await upload_qs.prefetch_related("collections")

    # Get upload from database
    if not len(upload_models):
        raise HTTPException(status_code=404, detail="None of the selected uploads provided exist.")

    # Add collection to the upload, creating the collection if it doesn't exist
    try:
        await Collection.add_or_create_for_uploads(
            uploads=upload_models, collection_name=collection_search, user_id=current_user.id
        )

    except ValueError as e:
        return await error_template_response(request, [str(e)], status_code=400)

    # Refresh relationships
    await asyncio.gather(*[upload.fetch_related("collections") for upload in upload_models])

    # Get selected collections
    selected_collections = await Collection.get_combined_for_uploads(user=current_user, uploads=upload_models)

    # Get collections with filter applied, excluding those already linked to the upload
    selected_collection_ids = set(c.id for c in selected_collections)
    filtered_collections = await Collection.filter(user=current_user) \
        .exclude(id__in=selected_collection_ids).limit(5).order_by("name")

    # Build response
    response = templates.TemplateResponse(
        request,
        "components/collections/macro_combo-selector.html.j2",
        context={
            "current_user": current_user,
            "selected_collections": selected_collections,
            "filtered_collections": filtered_collections,
        },
        status_code=201,
    )

    return response


@router.patch("", response_class=Response)
async def update_upload_collections_patch(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    collection_id: Annotated[int, Form()],
    state: Annotated[bool, Form()],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Update the collections linked to an upload based on a list of collection IDs."""
    
    # Confirm user owns the collection provided
    collection = await Collection.get_or_none(id=collection_id).prefetch_related("user")
    if collection is None or collection.user.id != current_user.id:
        error_message = f"Collection with ID {collection_id} not found or insufficient permissions."
        return await error_template_response(request, [error_message], status_code=400)

    # Get uploads from database including related collections
    upload_qs = build_readable_upload_queryset(
        current_user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )
    upload_models = await upload_qs.prefetch_related("collections")

    # Get upload from database
    if not len(upload_models):
        raise HTTPException(status_code=404, detail="None of the selected uploads provided exist.")

    # Add or remove based on state from client
    if state is True:
        for upload_model in upload_models:
            await collection.uploads.add(upload_model) # type: ignore
    else:
        for upload_model in upload_models:
            await collection.uploads.remove(upload_model) # type: ignore

    # Refresh relationships
    await asyncio.gather(*[upload.fetch_related("collections") for upload in upload_models])

    # Get selected collections
    selected_collections = await Collection.get_combined_for_uploads(user=current_user, uploads=upload_models)

    # Get collections with filter applied, excluding those already linked to the upload
    selected_collection_ids = set(c.id for c in selected_collections)
    filtered_collections = await Collection.filter(user=current_user) \
        .exclude(id__in=selected_collection_ids).limit(5).order_by("name")

    # Build response
    response = templates.TemplateResponse(
        request,
        "components/collections/combo-selector-items.html.j2",
        context={
            "current_user": current_user,
            "selected_collections": selected_collections,
            "filtered_collections": filtered_collections,
        },
        status_code=202,
    )

    return response
