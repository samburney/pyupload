from contextlib import asynccontextmanager

from tortoise import Tortoise, connections

from app.lib.config import get_app_config


config = get_app_config()

MODEL_MODULES = [
    "app.models.images",
    "app.models.legacy",
    "app.models.refresh_tokens",
    "app.models.users",
    "app.models.uploads",
]


@asynccontextmanager
async def init_db():
    """Initialize the Tortoise ORM with the application configuration.
    
    This is an async context manager that initializes the database connection
    on entry and closes it on exit.
    """
    await Tortoise.init(
        db_url=config.db_url,
        modules={"models": MODEL_MODULES},
    )
    try:
        yield
    finally:
        await connections.close_all()


# Early init for Pydantic model generation (schema only, no DB connection)
# This MUST be called before pydantic_model_creator() to ensure relationships
# are properly discovered and included in the generated Pydantic model.
Tortoise.init_models(MODEL_MODULES, "models")


# Import Pydantic schemas AFTER init_models() - this ensures relationships are included
# See: https://stackoverflow.com/a/65881146
from app.models.schemas import Upload_Pydantic  # noqa: E402

# Re-export commonly used models for convenience
# Usage: from app.models import Upload, Upload_Pydantic, User
from app.models.uploads import Upload  # noqa: E402
from app.models.users import User  # noqa: E402


TORTOISE_ORM = {
    "connections": {"default": config.db_url},
    "apps": {
        "models": {
            "models": MODEL_MODULES,
            "default_connection": "default",
        }
    },
}
