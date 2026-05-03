from typing import Annotated
from fastapi import APIRouter, UploadFile, Depends, HTTPException
from fastapi.responses import JSONResponse

from app.lib.error_handling import NotAuthorisedError, files_not_provided_exception
from app.lib.upload_handler import handle_uploaded_files

from app.models.uploads import Upload, UploadResult
from app.models.users import User

from app.api.auth import get_current_user


router = APIRouter(prefix="/uploads", tags=["uploads"])


@router.post("")
async def api_upload_create_post(
    current_user: Annotated[User, Depends(get_current_user)],
    upload_files: list[UploadFile]
) -> dict[str, list[UploadResult]]:
    """Handle multiple uploaded files."""

    if not upload_files or len(upload_files) == 0:
        raise files_not_provided_exception

    results = await handle_uploaded_files(user=current_user, files=upload_files)
    return {"results": results}


@router.delete("/{id}")
async def api_upload_delete(
    id: int,
    current_user: Annotated[User, Depends(get_current_user)],
) -> JSONResponse:
    """API endpoint to delete an uploaded file."""

    upload = await Upload.get_or_none(id=id).prefetch_related("user")
    if upload is None:
        raise HTTPException(status_code=404, detail="Upload not found.")

    # Validate user access to this file
    if not upload.is_owner(current_user):
        raise NotAuthorisedError("You do not have permission to delete this file.")

    # Delete the file
    await upload.delete()

    # Construct response
    result = {
        "status": "success",
        "message": "File deleted successfully."
    }

    return JSONResponse({"result": result}, status_code=200)
