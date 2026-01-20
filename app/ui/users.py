from typing import Annotated
from fastapi import APIRouter, Request, Response, Depends
from fastapi.responses import HTMLResponse

from app.lib.config import get_app_config

from app.models.users import User

from app.ui.common import templates
from app.ui.common.session import flash_message
from app.ui.common.security import get_current_authenticated_user, get_or_create_authenticated_user


config = get_app_config()
router = APIRouter(prefix="/users", tags=["users"])


@router.get("/me", response_class=HTMLResponse)
async def show_profile_page(
    request: Request,
    current_user: Annotated[User, Depends(get_or_create_authenticated_user)]
):
    """Render the users profile page."""
    return templates.TemplateResponse(request, "users/profile.html.j2", {"current_user": current_user})
