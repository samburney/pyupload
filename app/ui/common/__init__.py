from fastapi.templating import Jinja2Templates

from app.ui.common import security, session
from app.ui.common.session import get_flashed_messages


templates = Jinja2Templates(directory="app/ui/templates")
templates.env.globals['get_flashed_messages'] = get_flashed_messages


def error_response(request, error_messages, status_code=400):
    """Render an error response with given messages and status code."""
    return templates.TemplateResponse(
        request=request,
        name="common/messages.html.j2",
        context={"error_messages": error_messages},
        status_code=status_code,
    )


__all__ = ["security", "session"]
