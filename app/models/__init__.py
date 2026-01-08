from tortoise import Tortoise

from app.lib.config import get_app_config

app_config = get_app_config()

MODEL_MODULES = [
    "app.models.legacy",
    "app.models.users",
]

TORTOISE_ORM = {
    "connections": {"default": app_config.db_url},
    "apps": {
        "models": {
            "models": MODEL_MODULES,
            "default_connection": "default",
        }
    },
}

async def init_db():
    """Initialize the Tortoise ORM with the application configuration."""
    await Tortoise.init(config=TORTOISE_ORM)
