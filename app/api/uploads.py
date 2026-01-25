from typing import Annotated
from fastapi import APIRouter, UploadFile, Depends, HTTPException

from app.lib.upload_handler import handle_uploaded_files

from app.api.auth import get_current_user

from app.models.uploads import UploadResult
from app.models.users import User


router = APIRouter(prefix="/uploads", tags=["uploads"])


# Exception shortcut variables
files_not_provided_exception = HTTPException(
    status_code=400,
    detail="No files provided for upload."
)


@router.post("")
async def create_uploaded_files(
    current_user: Annotated[User, Depends(get_current_user)],
    upload_files: list[UploadFile]
) -> dict[str, list[UploadResult]]:
    """Handle multiple uploaded files."""

    if not upload_files or len(upload_files) == 0:
        raise files_not_provided_exception

    results = await handle_uploaded_files(user=current_user, files=upload_files)
    return {"results": results}
