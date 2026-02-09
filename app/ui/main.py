from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse
from tortoise.expressions import Q

from app.lib.config import get_app_config
from app.lib.auth import get_current_user_from_request
from app.ui.common import templates

from app.models.common.pagination import PaginationParams
from app.models.uploads import Upload, UploadSerializer


config = get_app_config()
router = APIRouter(tags=["main"])


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    pagination: Annotated[PaginationParams, Depends()],
):
    """Render the main index page."""
    
    current_user = await get_current_user_from_request(request)

    # If user is logged, include their private uploads
    # TODO: Make this a user configurable option
    if current_user:
        query = Q(private=False) | Q(user=current_user)
    else:
        query = Q(private=False)

    # Update item pagination parameter
    pagination.count = await Upload.filter(query).count()

    # Get uploads
    uploads_models = Upload.paginate(**pagination.page_data(), query=query).order_by("-created_at").limit(24).prefetch_related("user", "images")
    uploads = await UploadSerializer.from_queryset(uploads_models)

    print(pagination.model_dump())

    # Template context
    context = {
        "current_user": current_user,
        "uploads": uploads,
        "pagination": pagination,
    }

    return templates.TemplateResponse(request, "index.html.j2", context=context)
