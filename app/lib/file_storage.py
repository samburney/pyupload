import magic

from typing import BinaryIO
from fastapi import UploadFile

from app.lib.helpers import (
    split_filename,
    make_clean_filename,
    make_unique_filename,
)
from app.lib.config import get_app_config

from app.models.users import User
from app.models.uploads import Upload, UploadMetadata, UploadResult


config = get_app_config()


# User validation exceptions
class UserQuotaExceeded(Exception):
    """Exception raised when a user exceeds their upload quotas."""
    pass

class UserFileTypeNotAllowed(Exception):
    """Exception raised when a user uploads a disallowed file type."""
    pass


async def make_upload_metadata(user: User, file: UploadFile | BinaryIO, filename: str | None = None) -> UploadMetadata:
    """Build metadata for an uploaded file."""
    
    # Determine filename
    original_filename_with_extension = get_filename(file, filename)
    original_filename, ext = split_filename(original_filename_with_extension)
    clean_filename = make_clean_filename(original_filename)
    unique_filename = make_unique_filename(original_filename_with_extension)
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


def get_filename(file: UploadFile | BinaryIO, filename: str | None = None) -> str:
    """Get the filename from UploadFile or BinaryIO."""
    if isinstance(file, BinaryIO) and filename is None:
        raise ValueError("Uploaded file must have a filename.")

    # If provided, use the `filename` parameter
    if filename is None:
        if isinstance(file, UploadFile) and not file.filename:
            raise ValueError("Uploaded file must have a filename.")
        elif isinstance(file, UploadFile) and file.filename:
            filename = file.filename

    # Final check for filename
    if filename is None:
        raise RuntimeError("Filename cannot be None.")

    return filename


def get_file_instance(file: UploadFile | BinaryIO) -> BinaryIO:
    """Get a file-like object from UploadFile or BinaryIO."""

    # Handle FastAPI UploadFile
    if isinstance(file, UploadFile):
        return file.file
    return file


def get_file_size(file: BinaryIO | UploadFile) -> int:
    """Get the size of the uploaded file in bytes."""

    size: int = 0
    file_inst: BinaryIO = get_file_instance(file)
        
    # Save current position
    current_pos = file_inst.tell()
    file_inst.seek(0, 2)  # Move to end of file
    size = file_inst.tell()
    file_inst.seek(current_pos)  # Restore position

    return size


async def get_file_mime_type(file: BinaryIO | UploadFile) -> str:
    """Get the MIME type of the uploaded file."""
    # Get file size
    file_size = get_file_size(file)
    if file_size == 0:
        raise ValueError("Cannot determine MIME type of empty file.")

    # Get MIME type
    read_len = min(1024, file_size)

    if isinstance(file, UploadFile):
        current_pos = file.file.tell()
        await file.seek(0)
        mime_type = magic.from_buffer(await file.read(read_len), mime=True)
        await file.seek(current_pos)  # Reset file pointer after reading
    else:
        current_pos = file.tell()
        file.seek(0)
        mime_type = magic.from_buffer(file.read(read_len), mime=True)
        file.seek(current_pos)  # Reset file pointer after reading

    return mime_type


async def validate_user_filetypes(user: User, file: BinaryIO | UploadFile) -> bool:
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


async def validate_user_quotas(user: User, file: BinaryIO | UploadFile) -> bool:
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


async def add_uploaded_file(user: User, file: UploadFile | BinaryIO, filename: str | None = None) -> UploadResult:
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
        upload=upload,
        metadata=metadata,
    )

    return upload_result


async def save_uploaded_file(file: UploadFile | BinaryIO, metadata: UploadMetadata) -> bool:
    # Save the uploaded file to the generated path
    try:
        with metadata.filepath.open("wb") as dest:
            if isinstance(file, UploadFile):
                await file.seek(0)
                content = await file.read()
            else:
                file.seek(0)
                content = file.read()
            dest.write(content)

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
