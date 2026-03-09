from typing import Annotated
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse

from app.lib.config import get_app_config

from app.ui.gallery import gallery_index_get, GalleryPaginationDefaultParams


config = get_app_config()
router = APIRouter(tags=["main"])


@router.get("/", response_class=HTMLResponse)
async def index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
):
    """Render the main index page."""
    
    return await gallery_index_get(request, pagination)


@router.post("/update-window-dimensions")
async def update_window_dimensions(
    request: Request,
    width: Annotated[int, Form()],
    height: Annotated[int, Form()],
):
    """Endpoint to receive window dimensions from the client."""

    print(f"Received window dimensions: width={width}, height={height}")

    # Store dimensions in the session (or database if needed)
    request.session["window_width"] = width
    request.session["window_height"] = height

    return HTMLResponse(status_code=204)
