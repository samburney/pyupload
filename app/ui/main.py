import hashlib
from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse, Response
from tortoise.expressions import Q

from app.lib.config import get_app_config
from app.lib.auth import get_current_user_from_request

from app.ui.common.templating import templates

from app.models.common.pagination import PaginationParams
from app.models.uploads import Upload, UploadSerializer


config = get_app_config()
router = APIRouter(tags=["main"])


class HomePaginationParams(PaginationParams):
    """Default pagination parameters for the home page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "created_at"
    sort_order: str = "desc"
    page_size: int = 24


def get_home_page_etag(*, uploads: list[UploadSerializer], pagination: HomePaginationParams, user_id: int | None) -> str:
    """Build a weak ETag for the current home-page payload."""
    signature_parts = [
        str(user_id or 0),
        str(pagination.page),
        str(pagination.page_size),
        str(pagination.count),
    ]

    for upload in uploads:
        updated_at = upload.updated_at.isoformat() if upload.updated_at else ""
        signature_parts.append(f"{upload.id}:{updated_at}")

    digest = hashlib.sha1("|".join(signature_parts).encode("utf-8")).hexdigest()
    return f'W/"home-gallery-{digest}"'


@router.get("/", response_class=HTMLResponse)
async def index(
    request: Request,
    pagination: Annotated[HomePaginationParams, Depends()],
):
    """Render the main index page."""
    
    current_user = await get_current_user_from_request(request)

    # If user is logged, include their private uploads
    # TODO: Make this a user configurable option
    if current_user:
        query = Q(private=False) | Q(user=current_user)
    else:
        query = Q(private=False)

    # Update item pagination parameter
    pagination.count = await Upload.filter(query).count()

    # Get uploads
    uploads_models = Upload.paginate(**pagination.page_data(), query=query) \
        .prefetch_related("user", "images", "tags", "collections")
    uploads = await UploadSerializer.from_queryset(uploads_models)

    # Template context
    context = {
        "current_user": current_user,
        "uploads": uploads,
        "pagination": pagination,
    }

    etag = get_home_page_etag(
        uploads=uploads,
        pagination=pagination,
        user_id=current_user.id if current_user else None,
    )
    headers = {
        "Cache-Control": "private, max-age=60, must-revalidate",
        "ETag": etag,
        "Vary": "Cookie",
    }

    if_none_match = request.headers.get("if-none-match")
    if if_none_match:
        etag_values = [value.strip() for value in if_none_match.split(",")]
        if etag in etag_values or "*" in etag_values:
            return Response(status_code=304, headers=headers)

    response = templates.TemplateResponse(request, "index.html.j2", context=context)
    for key, value in headers.items():
        response.headers[key] = value

    return response


@router.get("/test", response_class=HTMLResponse)
async def test_get(
    request: Request,
    pagination: Annotated[HomePaginationParams, Depends()],
):
    """Render the main index page."""
    
    current_user = await get_current_user_from_request(request)

    collections = [
        "Wanderlust Chronicles",
        "Chasing Sunsets",
        "Passport Pages",
        "The Great Escape",
        "Miles and Memories",
        "A Year in the Life",
        "Everyday Magic",
        "The Little Things",
        "Growing Up Too Fast",
        "Our Beautiful Chaos",
        "Cheers to the Years",
        "A Night to Remember",
        "The Golden Hours",
        "Flashbacks & Festivities",
        "The Birthday Bash",
        "Paws and Play",
        "Into the Wild",
        "Seasons Change",
        "Tail Wags & Whiskers",
        "Through the Lens"
    ]

    return templates.TemplateResponse(request, "test.html.j2", context={"current_user": current_user, "collections": collections})
