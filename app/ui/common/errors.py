from fastapi import Request, Response
from fastapi.responses import HTMLResponse

from app.lib.config import logger
from app.lib.auth import get_current_user_from_request
from app.lib.error_handling import supports_error_image, get_error_image_response, ImageProcessingError

from app.ui.common.templating import templates


async def error_template_response(request: Request, error_messages: list[str], status_code: int = 400, title: str | None = None):
    """Render an error response with given messages and status code."""

    current_user = await get_current_user_from_request(request)

    return templates.TemplateResponse(
        request=request,
        name="layout/error.html.j2",
        context={
            "current_user": current_user,
            "error_messages": error_messages,
            "empty_content_title": title,
            "empty_content_message": error_messages[0] if error_messages else "",
        },
        status_code=status_code,
    )


async def error_response_for_get(
    *,
    filename: str | None = None,
    error_title: str,
    error_message: str,
    status_code: int,
    as_html: bool = False,
    request: Request | None = None,
) -> Response:
    """Return image error responses only for supported image conversion formats."""
    if not as_html and filename and supports_error_image(filename):
        try:
            return get_error_image_response(
                error_title=error_title,
                error_message=error_message,
                filename=filename,
                status_code=status_code,
            )
        except ImageProcessingError:
            logger.warning(
                "Falling back to HTML error response for unsupported image format: %s",
                filename,
            )

    if request is not None:
        return await error_template_response(
            request,
            [error_message],
            status_code=status_code,
            title=error_title,
        )

    return HTMLResponse(status_code=status_code)
