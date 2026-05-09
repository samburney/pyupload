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


async def _browse_crumbs(bc: Breadcrumbs, **_) -> None:
    bc.stack = []
    bc.push("Browse", str(bc.request.base_url))


Breadcrumbs.register("index_get", "gallery_index_get")(_browse_crumbs)


@Breadcrumbs.register("all_get", "gallery_all_get")
async def _all_crumbs(bc: Breadcrumbs, **_) -> None:
    # Produces: Browse > All
    bc.stack = []
    bc.push("Browse", str(bc.request.base_url))
    bc.push("All", str(bc.request.url_for("all_get")))


@Breadcrumbs.register("popular_get", "gallery_popular_get")
async def _popular_crumbs(bc: Breadcrumbs, **_) -> None:
    # Produces: Browse > Popular
    bc.stack = []
    bc.push("Browse", str(bc.request.base_url))
    bc.push("Popular", str(bc.request.url_for("popular_get")))


@Breadcrumbs.register("random_get", "gallery_random_get")
async def _random_crumbs(bc: Breadcrumbs, **_) -> None:
    # Produces: Browse > Random
    bc.stack = []
    bc.push("Browse", str(bc.request.base_url))
    bc.push("Random", str(bc.request.url_for("random_get")))


@router.get("/", response_class=HTMLResponse)
async def index_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the main index page."""

    await _browse_crumbs(breadcrumbs)

    return await gallery_index_get(request, pagination, breadcrumbs)


@router.get("/all", response_class=HTMLResponse)
async def all_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the all uploads gallery."""

    await _browse_crumbs(breadcrumbs)

    return await gallery_all_get(request, pagination, breadcrumbs)


@router.get("/popular", response_class=HTMLResponse)
async def popular_get(
    request: Request,
    pagination: Annotated[GalleryPaginationDefaultParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the popular uploads gallery."""

    await _browse_crumbs(breadcrumbs)

    return await gallery_popular_get(request, pagination, breadcrumbs)


@router.get("/random", response_class=HTMLResponse)
async def random_get(
    request: Request,
    pagination: Annotated[RandomGalleryPaginationParams, Depends()],
    breadcrumbs: Annotated[Breadcrumbs, Depends(breadcrumb_handler.handle_request)],
) -> Response:
    """Render the random uploads gallery."""

    await _browse_crumbs(breadcrumbs)

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
