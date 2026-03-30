import os
import logging

from dotenv import load_dotenv
from pathlib import Path
from functools import lru_cache

from app.lib.helpers import is_bool, validate_mime_types


PROJECT_ROOT = Path(__file__).parent.parent.parent
ENV_PATH = PROJECT_ROOT / ".env"
load_dotenv(dotenv_path=ENV_PATH)


def _resolve_storage_dir(env_var: str, default: str) -> Path:
    """Resolve a storage directory path from an env var, creating it if it does not exist."""
    path_str = os.getenv(env_var, default)
    path = Path(path_str).resolve() if path_str.startswith("/") else (PROJECT_ROOT / path_str).resolve()
    if not path.exists():
        logging.getLogger(__name__).info(f"Creating storage directory at {path}")
        path.mkdir(parents=True, exist_ok=True)
    if not path.is_dir():
        raise ValueError(f"{env_var} path '{path}' is not a directory.")
    return path


class AppConfig:
    """Application configuration loader."""

    # Debug and development configuration
    debug: bool = is_bool(os.getenv("DEBUG", "false")) == True

    # Set up shared logger for app
    if debug:
        logging.basicConfig(level=logging.INFO)
    logger = logging.getLogger(__name__)

    # Web server configuration
    app_host: str = os.getenv("APP_HOST", "0.0.0.0")
    app_port: int = int(os.getenv("APP_PORT", "8000"))
    app_default_domain: str = str(os.getenv("APP_DEFAULT_DOMAIN", "example.com"))
    app_reload: bool = is_bool(os.getenv("APP_RELOAD", "false")) == True
    app_base_url: str = os.getenv("APP_BASE_URL", f"http://{app_default_domain}:{app_port}")
    app_site_name: str = os.getenv("APP_SITE_NAME", "Simple Upload")

    # File storage configuration
    storage_path: Path = _resolve_storage_dir("STORAGE_PATH", "./data/files")
    storage_cache_retention_days: int = int(os.getenv("STORAGE_CACHE_RETENTION_DAYS", "30"))
    storage_orphaned_max_age_hours: int = int(os.getenv("STORAGE_ORPHANED_MAX_AGE_HOURS", "24"))
    if storage_orphaned_max_age_hours < 0:
        raise ValueError("STORAGE_ORPHANED_MAX_AGE_HOURS must be a non-negative integer.")

    # Archive configuration
    archive_storage_path: Path = _resolve_storage_dir("ARCHIVE_STORAGE_PATH", str(storage_path / "archives"))
    archive_max_age_hours: int = int(os.getenv("ARCHIVE_MAX_AGE_HOURS", "24"))
    if archive_max_age_hours <= 0:
        raise ValueError("ARCHIVE_MAX_AGE_HOURS must be a positive integer.")
    archive_zstd_level: int = int(os.getenv("ARCHIVE_ZSTD_LEVEL", "3"))
    if not (1 <= archive_zstd_level <= 22):
        raise ValueError("ARCHIVE_ZSTD_LEVEL must be between 1 and 22.")

    # Database configuration
    db_host = os.getenv("DB_HOST", "db")
    db_port = int(os.getenv("DB_PORT", "3306"))
    db_name = os.getenv("DB_NAME", "simplegallery")
    db_user = os.getenv("DB_USER", "simplegallery")
    db_pass = os.getenv("DB_PASSWORD", "")
    if db_pass == "":
        raise ValueError("DB_PASSWORD environment variable must be set for database access.")
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
        raise ValueError("AUTH_TOKEN_AGE_MINUTES must be a non-negative integer.")
    auth_refresh_token_age_days: int = int(os.getenv("AUTH_REFRESH_TOKEN_AGE_DAYS", "7"))
    if auth_refresh_token_age_days <= 0:
        raise ValueError("AUTH_REFRESH_TOKEN_AGE_DAYS must be a non-negative integer.")

    # User limits configuration
    user_max_file_size_mb: int = int(os.getenv("USER_MAX_FILE_SIZE_MB", "100"))
    user_max_uploads: int = int(os.getenv("USER_MAX_UPLOADS", "-1"))  # -1 for unlimited
    user_allowed_types: str = os.getenv("USER_ALLOWED_TYPES", "*")
    unregistered_max_file_size_mb: int = int(os.getenv("UNREGISTERED_MAX_FILE_SIZE_MB", "10"))
    unregistered_max_uploads: int = int(os.getenv("UNREGISTERED_MAX_UPLOADS", "5"))
    unregistered_allowed_types: str = os.getenv("UNREGISTERED_ALLOWED_TYPES", "image/jpeg,image/png,image/gif")
    unregistered_account_abandonment_days: int = int(os.getenv("UNREGISTERED_ACCOUNT_ABANDONMENT_DAYS", "90"))

    # Validate file size limits
    if user_max_file_size_mb <= 0 or unregistered_max_file_size_mb <= 0:
        raise ValueError("File size limits must be positive integers.")
    
    # Validate upload count limits
    if user_max_uploads < -1 or unregistered_max_uploads < -1:
        raise ValueError("Upload limits must be -1 (for unlimited) or a non-negative integer.")
    
    # Validate abandonment days
    if unregistered_account_abandonment_days <= -1:
        raise ValueError("UNREGISTERED_ACCOUNT_ABANDONMENT_DAYS must be -1 (for never) or a non-negative integer.")
    
    # Validate MIME types
    if not validate_mime_types(user_allowed_types):
        raise ValueError(f"USER_ALLOWED_TYPES contains invalid MIME type format: {user_allowed_types}")
    if not validate_mime_types(unregistered_allowed_types):
        raise ValueError(f"UNREGISTERED_ALLOWED_TYPES contains invalid MIME type format: {unregistered_allowed_types}")

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


# Set up module-level logger for easy access throughout app
logger = AppConfig.logger
