from asyncio import to_thread
from datetime import datetime, timedelta
from typing import BinaryIO
from tempfile import SpooledTemporaryFile

from fastapi import UploadFile

from app.lib.helpers import (
    split_filename,
    make_clean_filename,
    make_unique_filename,
)
from app.lib.config import get_app_config, logger
from app.lib.error_handling import UserQuotaExceeded, UserFileTypeNotAllowed, ImageInvalidError, ImageProcessingError
from app.lib.image_processing import process_uploaded_image
from app.lib.file_io import (
    delete_file,
    get_file_mime_type,
    get_file_size,
    get_filename,
)

from app.models.users import User
from app.models.uploads import Upload, UploadMetadata, UploadResult


config = get_app_config()


async def make_upload_metadata(user: User, file: UploadFile | BinaryIO | SpooledTemporaryFile, filename: str | None = None) -> UploadMetadata:
    """Build metadata for an uploaded file."""
    
    # Determine file names and attributes
    original_filename_with_extension = get_filename(file, filename)
    original_filename, ext = split_filename(original_filename_with_extension)
    clean_filename = make_clean_filename(original_filename)
    unique_filename = make_unique_filename(original_filename)
    size = get_file_size(file)
    mime_type = await get_file_mime_type(file)

    # Build metadata object
    metadata = UploadMetadata(
        user_id=user.id,
        filename=unique_filename,
        ext=ext,
        original_filename=original_filename,
        clean_filename=clean_filename,
        size=size,
        mime_type=mime_type,
    )

    return metadata



async def validate_user_filetypes(user: User, file: BinaryIO | UploadFile | SpooledTemporaryFile) -> bool:
    """Validate if the uploaded file's MIME type is allowed for the user."""

    allowed_mime_types = user.allowed_mime_types
    mime_type = await get_file_mime_type(file)

    # If user allows all types return True
    if '*' in allowed_mime_types:
        return True

    # Check if MIME type is allowed for the user
    allowed_types = user.allowed_mime_types
    if mime_type not in allowed_types:
        raise UserFileTypeNotAllowed(f"Uploaded file type '{mime_type}' is not allowed for this user.")

    return True


async def validate_user_quotas(user: User, file: UploadFile | BinaryIO | SpooledTemporaryFile) -> bool:
    """Validate if the user has enough quota for the uploaded file."""

    # Check against user quotas
    if user.max_file_size_mb == -1:
        return True  # No file size limit
    # Get filesize
    file_size = get_file_size(file) / (1024 * 1024)  # Convert bytes to Mbytes
    if file_size > user.max_file_size_mb:
        raise UserQuotaExceeded("Uploaded file exceeds maximum allowed file size for user.")
    
    if user.max_uploads_count == -1:
        return True  # No upload count limit
    if await user.uploads_count >= user.max_uploads_count:
        raise UserQuotaExceeded("User has exceeded the maximum number of allowed uploads.")

    return True


async def add_uploaded_file(user: User, file: UploadFile | BinaryIO | SpooledTemporaryFile, filename: str | None = None) -> UploadResult:
    """Add the uploaded file to storage and create a database record."""

    # Get a upload metadata object
    metadata = await make_upload_metadata(user, file, filename)

    # Save the uploaded file to the generated path
    await save_uploaded_file(file, metadata)

    # Create database record
    upload = await record_uploaded_file(metadata)

    # Make UploadResult object
    upload_result = UploadResult(
        status="success",
        message="File uploaded successfully.",
        upload_id=upload.id,
        metadata=metadata,
    )

    return upload_result


async def save_uploaded_file(file: UploadFile | BinaryIO | SpooledTemporaryFile, metadata: UploadMetadata) -> bool:
    # Save the uploaded file to the generated path
    try:
        with metadata.filepath.open("wb") as dest:
            if isinstance(file, SpooledTemporaryFile):
                file.seek(0)
                content = file.read()
            elif type(file).__name__ == 'UploadFile' and hasattr(file, 'file'):
                # UploadFile is async
                await file.seek(0)  # type: ignore
                content = await file.read()  # type: ignore
            else:
                # BinaryIO - sync
                file.seek(0)  # type: ignore
                content = file.read()  # type: ignore
            
            # Write content to destination file
            dest.write(content)  # type: ignore

            return True

    except Exception as e:
        raise IOError(f"Failed to save uploaded file: {e}")

    return False


async def record_uploaded_file(metadata: UploadMetadata) -> Upload:
    """Create a database record for the uploaded file."""

    # Build upload record data
    upload_data = {
        "user_id": metadata.user_id,
        "description": metadata.original_filename,
        "name": metadata.filename,
        "cleanname": metadata.clean_filename,
        "originalname": metadata.original_filename,
        "ext": metadata.ext,
        "size": metadata.size,
        "type": metadata.mime_type,
        "extra": "",
    }

    # Create upload record in database
    try:
        upload = await Upload.create(**upload_data)

    # Clean up file if database record creation fails
    except Exception as e:
        try:
            if metadata.filepath.exists():
                metadata.filepath.unlink()
        except Exception as cleanup_error:
            raise RuntimeError(f"Failed to create upload record and cleanup file: {cleanup_error}") from e

        raise RuntimeError(f"Failed to create upload record in database: {e}")

    return upload


async def process_uploaded_file(user: User, file: UploadFile | BinaryIO | SpooledTemporaryFile, filename: str | None = None) -> UploadResult:
    """Process the uploaded file and return its Upload record."""
    # Validate user constriants
    await validate_user_quotas(user, file)
    await validate_user_filetypes(user, file)

    # Add the uploaded file
    try:
        upload_result = await add_uploaded_file(user, file, filename)
    except Exception as e:
        raise RuntimeError(f"Failed to process uploaded file: {e}")
    
    # Attempt image processing
    if upload_result.status == "success" and upload_result.upload_id is not None:
        try:
            upload = await Upload.get(id=upload_result.upload_id)
            await process_uploaded_image(upload)
        
        # Ignore invalid image errors
        except ImageInvalidError as e:
            pass
        
        # Log image processing errors
        except ImageProcessingError as e:
            logger.warning(f"Image processing failed for upload ID {upload_result.upload_id}: {e}")

    return upload_result


async def cleanup_orphaned_files():
    """Clean up orphaned files (files on disk with no DB record)."""
    
    orphans_found = 0

    # Iterate through user directories
    user_directories = config.storage_path.glob("user_*")
    
    for user_dir in user_directories:
        # Skip if not a directory
        if not user_dir.is_dir():
            continue

        user_id = int(user_dir.name.split("_")[1])
        user_files = user_dir.glob("*")

        for file in user_files:
            # Skip if not a normal file
            if not file.is_file() or file.name.startswith("."):
                continue

            # Get file metadata
            file_stat = file.stat()
            file_age = datetime.fromtimestamp(file_stat.st_mtime)

            # Skip if file is too new
            if file_age > datetime.now() - timedelta(hours=config.storage_orphaned_max_age_hours):
                continue

            # Get file name parts
            file_name, file_ext = split_filename(file.name)

            # Check if file exists in database
            upload = await Upload.get_or_none(user_id=user_id, name=file_name, ext=file_ext)
            if upload is None:
                orphans_found += 1
                logger.info(f"Orphaned file found: {file.relative_to(config.storage_path)}")
                await to_thread(delete_file, file)
                
    return orphans_found
