from fastapi.templating import Jinja2Templates

from app.ui.common.session import get_flashed_messages


templates = Jinja2Templates(directory="app/ui/templates")
templates.env.globals['get_flashed_messages'] = get_flashed_messages
