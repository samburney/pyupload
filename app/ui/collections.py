import asyncio

from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response, HTMLResponse
from fastapi.exceptions import HTTPException

from app.models.collections import Collection
from app.models.users import User

from app.ui.common.breadcrumbs import Breadcrumbs
from app.ui.common.collections import CollectionSelectionDetail, CollectionPaginationDefaultParams
from app.ui.common.etag import (
    get_paginated_gallery_etag,
    check_etag_and_return_304_if_match,
    get_cache_headers,
)
from app.ui.common.responses import error_template_response, info_template_response
from app.ui.common.gallery import GalleryPaginationDefaultParams, get_request_context_filter
from app.ui.common.security import get_current_authenticated_user
from app.ui.common.templating import templates
from app.ui.common.uploads import (
    build_readable_upload_queryset,
)


router = APIRouter(prefix="/collections", tags=["collections"])
breadcrumb_handler = Breadcrumbs(router=router, route_title="Collections")


async def _get_collection_display_name(name_unique: str) -> str:
    collection = await Collection.get_or_none(name_unique=name_unique)
    return collection.name if collection else name_unique


@Breadcrumbs.register("collections_view_get")
async def _collection_view_crumbs(bc: Breadcrumbs, path_params: dict = {}, context: dict = {}, **_) -> None:
    bc.stack = []
    name_unique = path_params.get("name", "")
    display_name = context.get("collection_name") or await _get_collection_display_name(name_unique)
    if user := context.get("current_user"):
        bc.push(user.username, bc.request.url_for("show_profile_page"))
    bc.push("Collections", bc.request.url_for("collections_index_get"))
    bc.push(display_name, bc.request.url_for("collections_view_get", name=name_unique))


@router.get("", response_class=Response)
async def collections_index_get(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    pagination: Annotated[CollectionPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render collections gallery view"""

    collection_query = Collection.filter(user=current_user)
    pagination.count = await collection_query.count()

    collection_models = Collection.paginate(**pagination.page_data(), user=current_user)
    collections = await CollectionSelectionDetail.from_queryset(
        collection_models, context={"user": current_user}
    )

    breadcrumbs.replace(0, current_user.username, request.url_for("show_profile_page"))
    breadcrumbs.push(title="Collections", url=request.url_for("collections_index_get"))

    # Template context
    context = {
        "current_user": current_user,
        "breadcrumbs": breadcrumbs.get_all(),
        "stacks": collections,
        "pagination": pagination,
    }

    # Provide list of `selection_detail` as uploads to build a gallery etag
    uploads = [t.selection_detail for t in collections]
    etag = get_paginated_gallery_etag(
        request=request,
        uploads=uploads,
        pagination=pagination,
        user_id=current_user.id if current_user else None,
    )

    # Check if client already has current version
    not_modified = check_etag_and_return_304_if_match(request, etag)
    if not_modified:
        return not_modified

    # Build response with cache headers
    response = templates.TemplateResponse(request, "collections/index.html.j2", context=context)
    response.headers.update(get_cache_headers(etag=etag))

    return response


@router.get("/view/{name}", response_class=HTMLResponse)
async def collections_view_get(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    name: str, 
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render individual collection uploads gallery view"""

    collection_model = Collection.get(name_unique=name)
    collection = await CollectionSelectionDetail.from_single_queryset_or_none(collection_model, context={"user": current_user})

    if not collection:
        return await error_template_response(
            request, [f"Collection could not be found: {name}"], 404, "Collection not found."
        )

    # Update pagination count totals
    pagination.count = len(collection.readable_upload_models)
    if current_user:
        await collection.fetch_writable_upload_models(current_user)
        pagination.writable_count = len(collection.writable_upload_models) if collection.writable_upload_models else 0

    # Get uploads for this page
    await collection.fetch_readable_uploads(user=current_user, pagination=pagination)
    uploads = collection.readable_uploads
    if not uploads:
        return await info_template_response(
            request, ["This collection has no uploads yet."], 200, collection.name
        )

    await _collection_view_crumbs(breadcrumbs, path_params={"name": collection.name_unique}, context={
        "current_user": current_user,
        "collection_name": collection.name,
    })

    # Template context
    context = {
        "current_user": current_user,
        "breadcrumbs": breadcrumbs.get_all(),
        "uploads": uploads,
        "pagination": pagination,
        "enable_super_select": True,
    }

    etag = get_paginated_gallery_etag(
        request=request,
        uploads=uploads,
        pagination=pagination,
        user_id=current_user.id if current_user else None,
    )

    # Check if client already has current version
    not_modified = check_etag_and_return_304_if_match(request, etag)
    if not_modified:
        return not_modified

    # Build response with cache headers
    response = templates.TemplateResponse(request, "gallery/index.html.j2", context=context)
    response.headers.update(get_cache_headers(etag=etag))

    return response


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

    context_filter = await get_request_context_filter(request)
    upload_qs = build_readable_upload_queryset(
        user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
        context_filter=context_filter,
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

    context_filter = await get_request_context_filter(request)
    upload_qs = build_readable_upload_queryset(
        user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
        context_filter=context_filter,
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

    context_filter = await get_request_context_filter(request)
    upload_qs = build_readable_upload_queryset(
        user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
        context_filter=context_filter,
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
