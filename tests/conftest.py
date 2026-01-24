"""Pytest configuration and shared fixtures for pyupload tests."""

import os
import httpx
import pytest_asyncio
from asgi_lifespan import LifespanManager
from tortoise import Tortoise

# Ensure required environment variables are present before importing the app
os.environ.setdefault("AUTH_TOKEN_SECRET_KEY", "test_secret_key_for_testing_at_least_32_chars")
os.environ.setdefault("AUTH_TOKEN_ALGORITHM", "HS256")
os.environ.setdefault("AUTH_TOKEN_EXPIRE_MINUTES", "30")
os.environ.setdefault("AUTH_REFRESH_TOKEN_AGE_DAYS", "7")

from app import main  # noqa: E402
from app.models import users  # noqa: E402


@pytest_asyncio.fixture
async def client(monkeypatch):
    """Create an async HTTP client with in-memory test database."""
    async def init_test_db():
        await Tortoise.init(
            db_url="sqlite://:memory:",
            modules={"models": ["app.models.users", "app.models.refresh_tokens", "app.models.uploads", "app.models.images"]}
        )
        await Tortoise.generate_schemas()

    # Use an in-memory database during tests
    monkeypatch.setattr(main, "init_db", init_test_db)

    transport = httpx.ASGITransport(app=main.app)

    async with LifespanManager(main.app):
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as test_client:
            yield test_client

    await Tortoise.close_connections()


@pytest_asyncio.fixture
async def db():
    """Initialize in-memory SQLite database for unit tests."""
    await Tortoise.init(
        db_url="sqlite://:memory:",
        modules={"models": ["app.models.users", "app.models.refresh_tokens", "app.models.uploads", "app.models.images"]}
    )
    await Tortoise.generate_schemas()
    yield
    await Tortoise.close_connections()
