from asyncio import to_thread
from datetime import datetime, timedelta
from pathlib import Path
from typing import Callable, Literal, Self, Final

from app.lib.config import get_app_config, logger
from app.lib.helpers import clean_text
from app.lib.file_io import delete_file

from app.models import download_archives
from app.models.download_archives import DownloadArchive
from app.models.uploads import Upload, make_user_filepath


config = get_app_config()


class ArchiveCreationFailure(Exception):
    pass


class FileArchive:
    """Class to handle archival of Upload items"""

    def __init__(
        self: Self,
        download_archive: DownloadArchive,
        uploads: list[Upload],
        overwrite_existing: bool = False,
    ) -> None:

        # Make parameters available to class functions as constants
        self.download_archive: Final[DownloadArchive] = download_archive
        self.uploads: Final[list[Upload]] = uploads
        self.overwrite_existing: Final[bool] = overwrite_existing

        # Guard against malicious filesystem traversal
        self.archive_filename: Path = Path(download_archive.filename)
        if self.archive_filename.parent != Path("."):
            raise ValueError(f"`archive_path` contains directory components: {self.archive_filename}")

        self.archive_path: Final[Path] = config.archive_storage_path / self.archive_filename

        # Check if archive already exists
        if self.archive_path.exists():
            if self.archive_path.is_dir():
                raise IsADirectoryError(f"`archive_path` is a directory: {self.archive_filename}")
            if self.archive_path.is_file() and not overwrite_existing:
                raise ValueError(f"`archive_path` exists but `overwrite_existing` is not `True`: {self.archive_filename}")

        # Validate list over provided Uploads
        uploads_mismatch = {str(u.id) for u in uploads} ^ {str(u_id) for u_id in download_archive.upload_ids}
        if len(uploads_mismatch):
            raise ValueError(f"Provided uploads do not match archive upload_ids: {uploads_mismatch}")

        # Check each uploads file path
        for upload in uploads:
            upload_path = make_user_filepath(upload.user_id, upload.name).resolve() # type:ignore

            # Ensure resolved upload file path is inside configured storage path
            if not upload_path.is_relative_to(config.storage_path):
                raise ValueError(f'Upload path {upload_path} is outside upload storage directory')

            # Check upload file exists and is a normal file
            if not upload_path.exists() or not upload_path.is_file():
                raise FileNotFoundError(f"Upload path for {upload_path} could not be accessed or is not a file")

    def create_archive(self) -> None:
        """Proxy function to create an archive in various formats"""

        # Determine function to call
        archive_format = clean_text(self.download_archive.format, '')
        if not hasattr(self, f'create_{archive_format}_archive'):
            raise NotImplementedError(f'Archive format is not supported: {self.download_archive.format}')

        archive_function: Callable = getattr(self, f'create_{archive_format}_archive')

        # Call archive creation function
        archive_function()

    def create_zip_archive(self) -> None:
        """Create upload archive with in PKZIP format"""

        from zipfile import ZipFile

        with ZipFile(self.archive_path, 'w') as archive_file:
            for upload in self.uploads:
                upload_path = make_user_filepath(upload.user_id, upload.name) # type:ignore
                upload_filename = upload.originalname

                archive_file.write(filename=upload_path, arcname=upload_filename)

    def _create_tarball(self, mode: Literal['w:gz', 'w:bz2', 'w:xz']) -> None:
        """Internal method to handle tarball creation"""

        import tarfile

        with tarfile.open(name=self.archive_path, mode=mode) as archive_file:
            for upload in self.uploads:
                upload_path = make_user_filepath(upload.user_id, upload.name) # type:ignore
                upload_filename = upload.originalname

                archive_file.add(name=upload_path, arcname=upload_filename)

    def create_targz_archive(self) -> None:
        """Create GZIP compressed tarball from list of uploads"""

        self._create_tarball('w:gz')

    def create_tarbz2_archive(self) -> None:
        """Create BZIP compressed tarball from list of uploads"""

        self._create_tarball('w:bz2')

    def create_tarxz_archive(self) -> None:
        """Create XZ compressed tarball from list of uploads"""

        self._create_tarball('w:xz')

    def create_tarzstd_archive(self) -> None:
        """Create ZSTD compressed tarball from list of uploads"""

        import tarfile
        import zstandard

        # Stream tarball through zstandard compressor
        with self.archive_path.open('wb') as archive_file:
            compressor = zstandard.ZstdCompressor(level=config.archive_zstd_level)

            with compressor.stream_writer(archive_file) as stream_compressor:
                with tarfile.open(fileobj=stream_compressor, mode='w|') as tarball:
                    for upload in self.uploads:
                        upload_path = make_user_filepath(upload.user_id, upload.name) # type:ignore
                        upload_filename = upload.originalname

                        tarball.add(name=upload_path, arcname=upload_filename)


async def cleanup_orphaned_archives() -> int:
    """Clean up orphaned archive files (files on disk with no DB record)."""
    
    orphans_found = 0

    archive_storage_path = config.archive_storage_path
    archive_max_age_hours = config.archive_max_age_hours

    files = archive_storage_path.glob('*')

    for file in files:
        # Skip if not a normal file
        if not file.is_file() or file.name.startswith("."):
            continue

        # Get file metadata
        file_stat = file.stat()
        file_age = datetime.fromtimestamp(file_stat.st_mtime)

        # Skip if file is too new
        if file_age > datetime.now() - timedelta(hours=archive_max_age_hours):
            continue

        # Check if file exists in database
        download_archive_model = await DownloadArchive.get_or_none(filename=file.name)
        if download_archive_model is None:
            orphans_found += 1
            logger.info(f"Orphaned file found: {file.relative_to(config.archive_storage_path)}")
            await to_thread(delete_file, file)
                
    return orphans_found
