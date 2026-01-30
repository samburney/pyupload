from fastapi.templating import Jinja2Templates

from app.lib.config import get_app_config
from app.lib.helpers import sanitised_markdown, time_ago

from app.ui.common.session import get_flashed_messages


config = get_app_config()


def app_config_context_processor(request):
    """Context processor to add app config to templates."""
    return {"config": config}


templates = Jinja2Templates(
    directory="app/ui/templates",
    context_processors=[app_config_context_processor]
)
templates.env.globals['get_flashed_messages'] = get_flashed_messages
templates.env.filters['markdown'] = sanitised_markdown
templates.env.filters['ago'] = time_ago


def error_response(request, error_messages, status_code=400):
    """Render an error response with given messages and status code."""
    return templates.TemplateResponse(
        request=request,
        name="layout/messages.html.j2",
        context={"error_messages": error_messages},
        status_code=status_code,
    )


__all__ = ["security", "session"]
