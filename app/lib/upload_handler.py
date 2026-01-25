from fastapi import UploadFile

from app.lib.file_storage import process_uploaded_file

from app.models.users import User
from app.models.uploads import UploadResult


async def handle_uploaded_file(user: User, file: UploadFile) -> UploadResult:
    """Process the uploaded file and return its Upload record."""

    upload_result = await process_uploaded_file(user, file)

    return upload_result


async def handle_uploaded_files(user: User, files: list[UploadFile]) -> list[UploadResult]:
    """Process multiple uploaded files and return their Upload records."""
    upload_results: list[UploadResult] = []

    # Process list of files
    for file in files:
        # Handle each file individually
        try:
            result = await handle_uploaded_file(user, file)
            upload_results.append(result)

        # Return error result for failures
        except Exception as e:
            upload_results.append(
                UploadResult(
                    status="error",
                    message=str(e),
                    upload=None,
                    metadata=None,
                )
            )

    return upload_results
