from datetime import datetime, timedelta, timezone
from typing import Annotated
from fastapi import APIRouter, Request, Depends
from fastapi.responses import HTMLResponse

from app.lib.config import get_app_config

from app.models.common.pagination import PaginationParams
from app.models.download_archives import DownloadArchive, DownloadArchiveSerializer, DOWNLOAD_ARCHIVE_PREFETCH_MODELS
from app.models.users import User
from app.models.uploads import Upload, UploadSerializer, UPLOAD_PREFETCH_MODELS

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
) -> HTMLResponse:
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
        .prefetch_related(*UPLOAD_PREFETCH_MODELS)
    uploads = await UploadSerializer.from_queryset(upload_models)

    # Get list of non-expired download archives
    expiry_cutoff = datetime.now(tz=timezone.utc) - timedelta(hours=config.archive_max_age_hours)
    download_archive_models = DownloadArchive.filter(user=current_user, created_at__gte=expiry_cutoff).order_by('-created_at').prefetch_related(*DOWNLOAD_ARCHIVE_PREFETCH_MODELS)
    download_archives = await DownloadArchiveSerializer.from_queryset(download_archive_models)

    return templates.TemplateResponse(
        request,
        "users/profile.html.j2",
        {
            "current_user": current_user,
            "uploads": uploads,
            "pagination": pagination,
            "download_archives": download_archives,
        }
    )
