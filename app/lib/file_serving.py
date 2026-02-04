
from fastapi.responses import FileResponse

from app.lib.helpers import sanitise_filename

from app.models.uploads import Upload
from app.models.users import User


ALLOWED_INLINE_MIMETYPES = [
    "image/*",
    "video/*",
    "audio/*",
    "application/pdf",
    "text/plain",
]


class NotAuthorisedError(Exception):
    """Raised when a user is not authorised to access a file."""
    pass


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


async def serve_file(upload: Upload, filename: str | None = None, user: User | None = None, download: bool | None = False) -> FileResponse:
    """
    Serve a file with proper access control and view counter increment.
    """
    
    is_private = upload.is_private
    is_owner = user is not None and upload.is_owner(user)
    is_download = True

    # Check if the file is private and the user is not the owner
    if is_private and not is_owner:
        raise NotAuthorisedError("You do not have permission to access this file.")

    # Check that file exists
    if not upload.filepath.exists():
        raise FileNotFoundError("File not found.")

    # Sanitise filename
    santised_filename = sanitise_filename(filename) if filename is not None else None
    if santised_filename is not None:
        filename = santised_filename
    else:
        filename = upload.filename

    # Check if the file should be displayed inline
    if not download and is_inline_mimetype(upload.type):
        is_download = False
    
    # Increment view counter if the user is not the owner
    if not is_owner:
        upload.viewed += 1
        await upload.save()

    # Return file response
    response = FileResponse(upload.filepath, media_type=upload.type)
    response.headers["Content-Disposition"] = f"attachment; filename={filename}" if is_download else f"inline; filename={filename}"
    response.headers["Cache-Control"] = f"{'private' if is_private else 'public'}, max-age=3600"

    return response
