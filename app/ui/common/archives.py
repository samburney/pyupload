
from datetime import datetime, timezone, timedelta

from app.lib.config import get_app_config

from app.models.download_archives import DownloadArchive, DownloadArchiveSerializer, ArchiveStatusEnum
from app.models.uploads import Upload, UploadSerializer
from app.models.users import User


config = get_app_config()


async def get_selected_uploads_archives(
        uploads: list["Upload"] | list["UploadSerializer"],
        user: "User"
) -> list["DownloadArchiveSerializer"] | None:
    """Get existing download archives for a provided list of uploads"""

    # Match selected uploads against any existing DownloadArchives for this user
    selected_upload_ids = sorted(upload.id for upload in uploads)
    download_archive_expires_at = datetime.now(tz=timezone.utc) - timedelta(
        hours=config.archive_max_age_hours
    )
    download_archive_models = await (
        DownloadArchive.filter(
            user=user,
            created_at__gt=download_archive_expires_at,
            status__not=ArchiveStatusEnum.failed,
            upload_ids=selected_upload_ids,
        )
        .order_by("format", "-created_at")
        .prefetch_related("user")
        .limit(5)   # Max 5 archive formats currently supported.
    )

    if not len(download_archive_models):
        return None

    unique_download_archives_map: dict[str, DownloadArchive] = {}
    for download_archive in download_archive_models:
        if download_archive.format not in unique_download_archives_map:
            unique_download_archives_map[download_archive.format] = download_archive

    download_archive_models = list(unique_download_archives_map.values())
    download_archives = await DownloadArchiveSerializer.from_tortoise_instances(download_archive_models)

    return download_archives
