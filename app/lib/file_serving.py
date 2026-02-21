
from fastapi.responses import Response, FileResponse

from app.lib.helpers import sanitise_filename
from app.lib.error_handling import error_response_for_get, NotAuthorisedError, ImageProcessingError
from app.lib.image_processing import get_processed_image_path
from app.lib.config import logger

from app.models.images import IMAGE_FORMATS
from app.models.uploads import Upload
from app.models.users import User


ALLOWED_INLINE_MIMETYPES = [
    "image/*",
    "video/*",
    "audio/*",
    "application/pdf",
    "text/plain",
]


def is_inline_mimetype(mimetype: str) -> bool:
    """
    Check if a mimetype is allowed to be displayed inline.
    """
    for allowed in ALLOWED_INLINE_MIMETYPES:
        if allowed.endswith("/*"):
            if mimetype.startswith(allowed[:-1]):
                return True
        elif mimetype == allowed:
            return True
    return False


def validate_file_request(upload: Upload, user: User | None = None) -> bool:
    """
    Validate a file request based on access control and filename.
    """
    
    is_private = upload.is_private
    is_owner = user is not None and upload.is_owner(user)

    # Check if the file is private and the user is not the owner
    if is_private and not is_owner:
        raise NotAuthorisedError("You do not have permission to access this file.")

    # Check that file exists
    if not upload.filepath.exists():
        raise FileNotFoundError("File not found.")

    return True


async def serve_file(upload: Upload, filename: str | None = None, user: User | None = None, download: bool | None = False) -> Response:
    """
    Serve a file with proper access control and view counter increment.
    """
    
    is_private = upload.is_private
    is_owner = user is not None and upload.is_owner(user)
    is_download = True
    file_path = upload.filepath
    media_type = upload.type

    # Get related database records
    await upload.fetch_related("images")

    # Get sanitised filename
    santised_filename = sanitise_filename(filename) if filename is not None else None
    if santised_filename is not None:
        filename = santised_filename
    else:
        filename = upload.filename

    # Validate the file request
    try:
        validate_file_request(upload, user)
    except NotAuthorisedError as e:
        return error_response_for_get(
            error_title="Error 403: Unauthorized",
            error_message=f"An error occurred processing your request for {filename}: {e}",
            filename=filename,
            status_code=403,
        )
    except FileNotFoundError as e:
        return error_response_for_get(
            error_title="Error 404: File not found",
            error_message=f"An error occurred processing your request for {filename}: {e}",
            filename=filename,
            status_code=404,
        )

    # Handle image processing if requested based on filename
    try:
        if upload.is_image and media_type in IMAGE_FORMATS.values():
            processed_file_path = await get_processed_image_path(upload, filename)

            if processed_file_path is not None:
                file_path = processed_file_path
                media_type = IMAGE_FORMATS[file_path.suffix.lower()]
    except KeyError:
        return error_response_for_get(
            error_title="Error 422: Unprocessable Content",
            error_message=f"An error occurred processing your request for {filename}: Unsupported output format.",
            filename=filename,
            status_code=422,
        )
    except ImageProcessingError as e:
        return error_response_for_get(
            error_title="Error 422: Unprocessable Content",
            error_message=f"An error occurred processing your request for {filename}: {e}",
            filename=filename,
            status_code=422,
        )
    except Exception as e:
        logger.error(f"Unexpected image processing error for {upload.id}/{filename}: {e}", exc_info=True)
        return error_response_for_get(
            error_title="Error 500: Internal Server Error",
            error_message=f"An internal server error occurred processing your request for {filename}.",
            filename=filename,
            status_code=500,
        )

    # Check if the file should be displayed inline
    if not download and is_inline_mimetype(media_type):
        is_download = False
    
    # Increment view counter if the user is not the owner
    if not is_owner:
        upload.viewed += 1
        await upload.save()

    # Return file response
    try:
        response = FileResponse(file_path, media_type=media_type)
    except FileNotFoundError:
        return error_response_for_get(
            error_title="Error 404: File not found",
            error_message=f"The requested file, {filename} could not be found on this server.",
            filename=filename,
            status_code=404,
        )
    except Exception as e:
        logger.error(f"Unexpected file response error for {upload.id}/{filename}: {e}", exc_info=True)
        return error_response_for_get(
            error_title="Error 500: Internal Server Error",
            error_message=f"An internal server error occurred processing your request for {filename}.",
            filename=filename,
            status_code=500,
        )

    response.headers["Content-Disposition"] = f"attachment; filename={filename}" if is_download else f"inline; filename={filename}"
    response.headers["Cache-Control"] = f"{'private' if is_private else 'public'}, max-age=3600"

    return response
