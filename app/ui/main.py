from typing import Annotated
from fastapi import APIRouter, Request, Depends, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from starlette.responses import Response

from app.lib.config import get_app_config

from app.ui.common.breadcrumbs import Breadcrumbs

from app.ui.gallery import gallery_index_get
from app.ui.common.gallery import GalleryPaginationDefaultParams


config = get_app_config()
router = APIRouter(tags=["main"])
breadcrumb_handler = Breadcrumbs(router=router)


@router.get("/popular", response_class=HTMLResponse)
@router.get("/all", response_class=HTMLResponse)
@router.get("/", response_class=HTMLResponse)
async def index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the main index page."""
    
    breadcrumbs.push(title="Browse", url=f"{request.base_url}")

    return await gallery_index_get(request, pagination, breadcrumbs)


@router.get("/random", response_class=RedirectResponse)
async def random_get(
    request: Request
) -> RedirectResponse:
    """Redirect to gallery random page"""

    return RedirectResponse('/gallery/random', status_code=302)


@router.post("/update-window-dimensions")
async def update_window_dimensions(
    request: Request,
    width: Annotated[int, Form()],
    height: Annotated[int, Form()],
) -> HTMLResponse:
    """Endpoint to receive window dimensions from the client."""

    print(f"Received window dimensions: width={width}, height={height}")

    # Store dimensions in the session (or database if needed)
    request.session["window_width"] = width
    request.session["window_height"] = height

    return HTMLResponse(status_code=204)
