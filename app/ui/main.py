from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.lib.config import get_app_config
from app.lib.session_auth import SessionAuthHandler
from app.ui.common import templates

from app.models.users import UserPydantic

config = get_app_config()
router = APIRouter(tags=["main"])
session_auth = SessionAuthHandler(secret_key=config.session_secret_key)


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    current_user: Annotated[UserPydantic, Depends(session_auth.get_current_user)]):

    print("Current user in index:", current_user)

    return templates.TemplateResponse("index.html.j2", {"request": request, "current_user": current_user})
