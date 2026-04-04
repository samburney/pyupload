from typing import Annotated

from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import Response, HTMLResponse

from app.lib.helpers import make_clean_tag

from app.models.tags import Tag, get_combined_tags_for_uploads
from app.models.users import User

from app.ui.common.errors import error_template_response
from app.ui.common.security import get_current_authenticated_user
from app.ui.common.templating import templates
from app.ui.common.uploads import (
    get_readable_selected_upload_models,
)


router = APIRouter(prefix="/tags", tags=["tags"])


@router.post("/suggestions", response_class=HTMLResponse)
async def get_tag_suggestions_post(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    tag_search: Annotated[str, Form()] = "",
    tag_name: Annotated[list[str], Form()] = [],
) -> Response:
    """Get tag suggestions for current upload, filtered by the current input value."""

    if tag_search == "":
        return Response(status_code=204)  # Return empty response if input is empty to avoid unnecessary database query

    # Pluraise variable name for clarity
    selected_tags = tag_name

    # Get tag suggestions
    new_tag = None
    suggested_tags = await Tag.all().filter(name__icontains=tag_search) \
        .exclude(name__in=selected_tags)[:5] \
        .values_list("name", flat=True)

    if tag_search not in suggested_tags:
        new_tag = make_clean_tag(tag_search)

    return templates.TemplateResponse(
        request,
        "components/tags/suggestions.html.j2",
        context={
            "new_tag": new_tag,
            "suggested_tags": suggested_tags,
        },
    )


@router.post("/update", response_class=Response)
async def upload_add_tag_post(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    request: Request,
    tag_name: Annotated[str, Form()],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Add a tag to an upload."""
    
    # Get uploads from database
    upload_models = await get_readable_selected_upload_models(
        current_user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )

    for upload_model in upload_models:
        try:
            # Add tag to the upload, creating the tag if it doesn't exist
            await Tag.add_or_create_for_upload(upload_model, tag_name)
            await upload_model.fetch_related("tags")

        except ValueError as e:
            return await error_template_response(request, [str(e)], status_code=400)

    if len(upload_models) == 1:
        tags = upload_models[0].tags
    else:
        tags = get_combined_tags_for_uploads(upload_models)

    response = templates.TemplateResponse(
        request,
        "components/tags/input.html.j2",
        context={"current_user": current_user, "tags": tags},
        status_code=200,
    )

    return response


@router.post("/delete", response_class=Response)
async def upload_remove_tag_delete(
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    request: Request,
    tag_name: Annotated[str, Form()],
    super_selected: Annotated[bool, Form()] = False,
    selected_ids: Annotated[list[int], Form()] = [],
    deselected_ids: Annotated[list[int], Form()] = [],
) -> Response:
    """Remove a tag from an upload."""
    
    # Get upload from database
    upload_models = await get_readable_selected_upload_models(
        current_user=current_user,
        super_selected=super_selected,
        selected_ids=selected_ids,
        deselected_ids=deselected_ids,
    )

    for upload_model in upload_models:
        try:
            await Tag.remove_tag_from_upload(upload_model, tag_name)
            await upload_model.fetch_related("tags")

        except ValueError as e:
            return await error_template_response(request, [str(e)], status_code=400)

    if len(upload_models) == 1:
        tags = upload_models[0].tags
    else:
        tags = get_combined_tags_for_uploads(upload_models)

    response = templates.TemplateResponse(
        request,
        "components/tags/input.html.j2",
        context={"current_user": current_user, "tags": tags},
        status_code=200,
    )

    return response
