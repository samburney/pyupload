from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse
from tortoise.expressions import Q

from app.lib.config import get_app_config
from app.lib.auth import get_current_user_from_request
from app.ui.common import templates

from app.models.uploads import Upload, UploadSerializer


config = get_app_config()
router = APIRouter(tags=["main"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main index page."""
    
    current_user = await get_current_user_from_request(request)

    # If user is logged, include their private uploads
    # TODO: Make this a user configurable option
    if current_user:
        query = Q(private=False) | Q(user=current_user)
    else:
        query = Q(private=False)

    # Get uploads
    uploads_models = Upload.filter(query).order_by("-created_at").limit(24).prefetch_related("images")
    uploads = await UploadSerializer.from_queryset(uploads_models)
 
    return templates.TemplateResponse(request, "index.html.j2", {"current_user": current_user, "uploads": uploads})
