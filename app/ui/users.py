from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.lib.config import get_app_config

from app.models.common.pagination import PaginationParams
from app.models.users import User
from app.models.uploads import Upload, UploadSerializer

from app.ui.common.templating import templates
from app.ui.common.security import flash_message
from app.ui.common.security import get_current_authenticated_user


config = get_app_config()
router = APIRouter(tags=["users"])


class ProfilePaginationParams(PaginationParams):
    """Pagination parameters for the profile page."""

    # Override default sort_by and sort_order if not specified
    sort_by: str = "created_at"
    sort_order: str = "desc"


@router.get("/profile", response_class=HTMLResponse)
async def show_profile_page(
    request: Request,
    current_user: Annotated[User, Depends(get_current_authenticated_user)],
    pagination: Annotated[ProfilePaginationParams, Depends()],
):
    """Render the users profile page."""

    # Show warning if user is not registered
    if not current_user.is_registered:
        flash_message(
            request,
            message = """
You are currently logged in with a temporary, limited, user session.

If you would like to upgrade to a full account, please [login](/login) or [register](/register).
        """,
            message_type="warning",
        )

    # Update item pagination parameter
    pagination.count = await Upload.filter(user=current_user).count()

    # Get list of files uploaded
    upload_models = Upload.paginate(**pagination.page_data(), user=current_user) \
        .prefetch_related("user", "images", "tags", "collections")
    uploads = await UploadSerializer.from_queryset(upload_models)

    return templates.TemplateResponse(
        request,
        "users/profile.html.j2",
        {
            "current_user": current_user,
            "uploads": uploads,
            "pagination": pagination,
        }
    )
