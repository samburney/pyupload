import asyncio
from datetime import datetime, timedelta, timezone

from uuid import UUID
from typing import TYPE_CHECKING
from enum import Enum

from tortoise import fields, models
from tortoise_serializer import ModelSerializer

from app.lib.config import get_app_config
from app.lib.file_io import delete_file

from app.models.common.base import TimestampMixin
from app.models.users import UserSerializer


config = get_app_config()


class ArchiveStatusEnum(str, Enum):
    pending = 'pending'
    processing = 'processing'
    ready = 'ready'
    failed = 'failed'


class ArchiveFormatsEnum(str, Enum):
    zip = 'zip'
    tar_gzip = 'tar.gz'
    gzip = 'tar.gz'
    tarball = 'tar.gz'
    tar_bzip = 'tar.bz2'
    bzip = 'tar.bz2'
    bzip2 = 'tar.bz2'
    tar_xz = 'tar.xz'
    xz = 'tar.xz'
    tar_zstd = 'tar.zstd'
    zstd = 'tar.zstd'
    zstandard = 'tar.zstd'


class DownloadArchive(models.Model, TimestampMixin):
    id = fields.UUIDField(primary_key=True)
    user = fields.ForeignKeyField(
        "models.User", related_name="download_archives", on_delete=fields.CASCADE)
    upload_ids = fields.JSONField()
    filename = fields.CharField(max_length=255)
    format = fields.CharEnumField(enum_type=ArchiveFormatsEnum,
                                  default=ArchiveFormatsEnum.zip)
    status = fields.CharEnumField(enum_type=ArchiveStatusEnum,
                                  default=ArchiveStatusEnum.pending)

    class Meta:  # type: ignore[override]
        table = "download_archives"

    async def delete(self, using_db = None) -> None:
        """Delete the file from disk and its related database record."""

        await super().delete(using_db=using_db)
        await asyncio.to_thread(delete_file, config.archive_storage_path / self.filename)

    @classmethod
    async def cleanup_expired(cls) -> int:
        """Delete expired upload archives.
        
        Should be run periodically as a maintenance task.
        
        Returns:
            Number of archive files deleted
        """

        now = datetime.now(timezone.utc)
        expiry_timestamp = now - timedelta(hours=config.archive_max_age_hours)
        expired_archives = await cls.filter(created_at__lt=expiry_timestamp).all()
        
        count = len(expired_archives)
        for archive in expired_archives:
            await archive.delete()
        
        return count


class DownloadArchiveSerializer(ModelSerializer[DownloadArchive]):
    """Serializer for the DownloadArchive model."""

    # Model fields
    id: UUID
    user: UserSerializer
    upload_ids: str
    filename: str
    format: ArchiveFormatsEnum
    status: ArchiveStatusEnum
