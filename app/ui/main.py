from fastapi import APIRouter, Request
from fastapi.responses import HTMLResponse

from app.ui.common import templates


router = APIRouter(tags=["main"])


@router.get("/", response_class=HTMLResponse)
async def index(request: Request):
    return templates.TemplateResponse("index.html.j2", {"request": request})
