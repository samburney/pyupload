from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.lib.config import get_app_config
from app.lib.auth import get_current_user_from_request
from app.ui.common import templates


config = get_app_config()
router = APIRouter(tags=["main"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """Render the main index page."""
    
    current_user = await get_current_user_from_request(request)

    return templates.TemplateResponse(request, "index.html.j2", {"current_user": current_user})
