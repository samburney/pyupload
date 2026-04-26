from typing import Annotated

from fastapi import APIRouter, Depends, Form, Request
from fastapi.responses import HTMLResponse
from starlette.responses import Response

from app.ui.common.breadcrumbs import Breadcrumbs
from app.ui.common.gallery import (
    GalleryPaginationDefaultParams,
    RandomGalleryPaginationParams,
)
from app.ui.gallery import (
    gallery_all_get,
    gallery_index_get,
    gallery_popular_get,
    gallery_random_get,
)


router = APIRouter(tags=["main"])
breadcrumb_handler = Breadcrumbs(router=router)


@router.get("/", response_class=HTMLResponse)
async def index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the main index page."""

    breadcrumbs.push(title="Browse", url=f"{request.base_url}")

    return await gallery_index_get(request, pagination, breadcrumbs)


@router.get("/all", response_class=HTMLResponse)
async def all_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the all uploads gallery."""

    breadcrumbs.push(title="Browse", url=f"{request.base_url}")

    return await gallery_all_get(request, pagination, breadcrumbs)


@router.get("/popular", response_class=HTMLResponse)
async def popular_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the popular uploads gallery."""

    breadcrumbs.push(title="Browse", url=f"{request.base_url}")

    return await gallery_popular_get(request, pagination, breadcrumbs)


@router.get("/random", response_class=HTMLResponse)
async def random_get(
    request: Request,
    pagination: Annotated[RandomGalleryPaginationParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the random uploads gallery."""

    breadcrumbs.push(title="Browse", url=f"{request.base_url}")

    return await gallery_random_get(request, pagination, breadcrumbs)


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
