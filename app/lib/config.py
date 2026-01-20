import os
import logging

from dotenv import load_dotenv
from pathlib import Path
from functools import lru_cache

from app.lib.helpers import is_bool


PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)

logger = logging.getLogger(__name__)

class AppConfig:
    """Application configuration loader."""

    # Web server configuration
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_default_domain: str = str(os.getenv("APP_DEFAULT_DOMAIN", "example.com"))
    app_reload: bool = is_bool(os.getenv("APP_RELOAD", "false")) == True
    app_base_url: str = os.getenv("APP_BASE_URL", f"http://localhost:{app_port}")

    # Database configuration
    db_host = os.getenv("DB_HOST", "db")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_name = os.getenv("DB_NAME", "radius_app")
    db_user = os.getenv("DB_USER", "radius_user")
    db_pass = os.getenv("DB_PASSWORD", "radius_pass")
    db_pool_min_size: int = int(os.getenv("DB_POOL_MIN_SIZE", "1"))
    db_pool_max_size: int = int(os.getenv("DB_POOL_MAX_SIZE", "20"))
    db_connect_timeout: int = int(os.getenv("DB_CONNECT_TIMEOUT", "10"))

    # Authentication configuration
    auth_token_secret_key: str = os.getenv("AUTH_TOKEN_SECRET_KEY", "")
    if not auth_token_secret_key:
        raise ValueError("AUTH_TOKEN_SECRET_KEY environment variable must be set for session security.")
    auth_token_algorithm: str = os.getenv("AUTH_TOKEN_ALGORITHM", "HS256")
    auth_token_age_minutes: int = int(os.getenv("AUTH_TOKEN_AGE_MINUTES", "30"))
    if auth_token_age_minutes <= 0:
        raise ValueError("AUTH_TOKEN_AGE_MINUTES must be a positive integer.")
    auth_refresh_token_age_days: int = int(os.getenv("AUTH_REFRESH_TOKEN_AGE_DAYS", "7"))
    if auth_refresh_token_age_days <= 0:
        raise ValueError("AUTH_REFRESH_TOKEN_AGE_DAYS must be a positive integer.")

    # Adminer configuration - only really for dev use
    adminer_host: str = os.getenv("ADMINER_HOST", "localhost")
    adminer_port: int = int(os.getenv("ADMINER_HOST_PORT", "8082"))

    @property
    def db_url(self) -> str:
        """Construct the database URL from individual components."""
        return f"mysql://{self.db_user}:{self.db_pass}@{self.db_host}:{self.db_port}/{self.db_name}"


@lru_cache(maxsize=1)
def get_app_config() -> AppConfig:
    """Get the application configuration."""
    return AppConfig()
