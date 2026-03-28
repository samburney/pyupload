import asyncio
from datetime import date, datetime, timezone

from pathlib import Path
from uuid import UUID

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from app.lib.config import get_app_config, logger
from app.lib.file_archive import FileArchive, cleanup_orphaned_archives
from app.lib.file_storage import cleanup_orphaned_files

from app.models.download_archives import DownloadArchive, ArchiveStatusEnum
from app.models.refresh_tokens import RefreshToken
from app.models.uploads import Upload
from app.models.users import mark_abandoned


config = get_app_config()
scheduler = AsyncIOScheduler()


async def cleanup_tokens_job() -> None:
    """Clean up expired tokens"""
    expired = await RefreshToken.cleanup_expired()
    logger.info(f"Cleanup: {expired} expired tokens removed.")

# Schedule to trigger on the hour every hour with jitter up to 300 seconds
scheduler.add_job(cleanup_tokens_job, 'cron', hour='*', minute=0, jitter=300)


async def cleanup_abandoned_users_job() -> None:
    """Clean up abandoned users who never completed registration"""

    abandoned_count: int = 0

    # Mark abandoned users and get count
    try:
        abandoned_count = await mark_abandoned()
    except Exception as e:
        logger.error(f"Cleanup: Error during abandoned user cleanup: {e}")

    # TODO: Implement deletion of files owned by abandoned users, and marked as private.

    logger.info(f"Cleanup: {abandoned_count} abandoned users marked.")

# Schedule to trigger on the hour every hour with jitter up to 300 seconds
scheduler.add_job(cleanup_abandoned_users_job, 'cron', hour='*', minute=0, jitter=300)


async def cleanup_orphaned_files_job() -> None:
    """Clean up orphaned files"""

    orphaned_count: int = 0

    # Mark abandoned users and get count
    try:
        orphaned_count = await cleanup_orphaned_files()
    except Exception as e:
        logger.error(f"Cleanup: Error during orphaned file cleanup: {e}")

    logger.info(f"Cleanup: {orphaned_count} orphaned files found and removed.")

# Schedule to trigger on the hour every hour with jitter up to 300 seconds
scheduler.add_job(cleanup_orphaned_files_job, 'cron', hour='*', minute=0, jitter=300)


async def _mark_download_archive_failed(download_archive_model: DownloadArchive, message: str | None = None) -> None:
    """Helper function to log and mark a download archive job as failed"""

    if not message:
        message = f"Archive job failed: {download_archive_model.id}"

    # Log failure
    logger.error(message)

    # Update model with failure
    download_archive_model.status = ArchiveStatusEnum.failed
    await download_archive_model.save()


async def run_archive_job(download_archive_id: UUID) -> None:
    """Create upload archive file in background task"""

    # Get archive request details from database
    download_archive_model = await DownloadArchive.get_or_none(id=download_archive_id, status=ArchiveStatusEnum.pending)
    if not download_archive_model:
        logger.error(f"Download archive could not be found: {download_archive_id}")
        return

    # Fetch list of Upload models
    upload_models: list[Upload] = list()
    for u_id in download_archive_model.upload_ids:
        upload_model = await Upload.get_or_none(id=u_id)

        if not upload_model:
            await _mark_download_archive_failed(
                download_archive_model=download_archive_model,
                message=f"Upload specified cannot be found: {u_id}"
            )
            return 
        
        upload_models.append(upload_model)

    # Begin archival process
    try:
        file_archiver = FileArchive(download_archive=download_archive_model,
                                    uploads=upload_models,
                                    overwrite_existing=True)
        download_archive_model.status = ArchiveStatusEnum.processing
        await download_archive_model.save()
    
        # Start archive file creation
        await asyncio.to_thread(file_archiver.create_archive)

    # Handle failed archival
    except Exception as e:
        await _mark_download_archive_failed(
            download_archive_model=download_archive_model,
            message=f"Archive job failed for {download_archive_model.id}: {e}"
        )
        return

    # Sanity check created file and update status
    download_archive_path: Path = config.archive_storage_path / Path(download_archive_model.filename).name
    if download_archive_path.exists() and download_archive_path.stat().st_size > 0:
        download_archive_model.status = ArchiveStatusEnum.ready
        await download_archive_model.save()
    else:
        await _mark_download_archive_failed(download_archive_model)
        return


def schedule_archive_job(download_archive_id: UUID, run_date: date | datetime | str = 'now') -> None:
    """Schedule upload archive creation"""

    if run_date == 'now':
        run_date = datetime.now(tz=timezone.utc)

    scheduler.add_job(func=run_archive_job, trigger='date', run_date=run_date, kwargs={"download_archive_id": download_archive_id})


async def cleanup_archives_job() -> None:
    """Cleanup expired and orphaned archive files"""

    # Run database cleanup task
    expired_count = await DownloadArchive.cleanup_expired()
    logger.info(f"Cleanup: {expired_count} expired upload archives removed.")

    # Run filesystem orphans cleanup
    orphaned_count = await cleanup_orphaned_archives()
    logger.info(f"Cleanup: {orphaned_count} orphaned files found and removed.")


# Schedule to trigger on the hour every hour with jitter up to 300 seconds
scheduler.add_job(cleanup_archives_job, 'cron', hour='*', minute=0, jitter=300)
