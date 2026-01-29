from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.lib.config import get_app_config

from app.models.users import User

from app.ui.common import templates
from app.ui.common.security import flash_message
from app.ui.common.security import get_or_create_authenticated_user


config = get_app_config()
router = APIRouter(tags=["users"])


@router.get("/profile", response_class=HTMLResponse)
async def show_profile_page(
    request: Request,
    current_user: Annotated[User, Depends(get_or_create_authenticated_user)]
):
    """Render the users profile page."""

    if not current_user.is_registered:
        flash_message(
            request,
            message = """
You are currently logged in with a temporary, limited, user session.

If you would like to upgrade to a full account, please [login](/login) or [register](/register).
        """,
            message_type="warning",
        )

    return templates.TemplateResponse(request, "users/profile.html.j2", {"current_user": current_user})
