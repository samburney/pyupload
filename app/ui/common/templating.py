import json

from fastapi import Request
from fastapi.templating import Jinja2Templates

from app.lib.config import get_app_config
from app.lib.helpers import sanitised_markdown, time_ago, humanize_bytes, split_filename

from app.ui.common.session import get_flashed_messages


config = get_app_config()


def app_config_context_processor(request: Request):
    """Context processor to add app config to templates."""

    context = {
        "config": config,
        "sidebar_open": request.cookies.get("sidebar_open", "true") == "true",
    }

    return context


templates = Jinja2Templates(
    directory="app/ui/templates",
    context_processors=[app_config_context_processor]
)
templates.env.globals['get_flashed_messages'] = get_flashed_messages
templates.env.filters['markdown'] = sanitised_markdown
templates.env.filters['ago'] = time_ago
templates.env.filters['humanize_bytes'] = humanize_bytes
templates.env.filters['split_filename'] = split_filename
templates.env.filters['parse_json'] = json.loads
