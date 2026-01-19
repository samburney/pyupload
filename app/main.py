from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.lib.config import get_app_config
from app.lib.scheduler import scheduler
from app.middleware.token_refresh import TokenRefreshMiddleware

from app.models import init_db

from app import api
from app import ui


config = get_app_config()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # App startup
    # Initialize Tortoise ORM
    await init_db()

    # Start scheduler
    scheduler.start()

    # App running
    yield

    # App shutdown
    # Stop scheduler
    scheduler.shutdown()


# Init FastAPI app
app = FastAPI(
    title="pyupload",
    lifespan=lifespan,
)

# Middleware
# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=config.auth_token_secret_key,
    session_cookie="pyupload_session",
    max_age=24 * 60 * 60,  # days to seconds
    path=config.session_file_path,
)

# Token refresh middleware
app.add_middleware(TokenRefreshMiddleware)

# App routes
# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API routes
app.include_router(api.auth.router, prefix='/api/v1')

# UI routes
app.include_router(ui.main.router, include_in_schema=False)
app.include_router(ui.auth.router, include_in_schema=False)


# Development environment links
@app.get("/", response_class=HTMLResponse)
async def read_root():
    adminer_host = 'localhost' if '0.0.0.0' == config.adminer_host else config.adminer_host
    adminer_port = config.adminer_port
    
    return f"""
    <html>
        <head>
            <title>pyupload</title>
            <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
        </head>
        <body class="container mt-5">
            <h1 class="text-primary">Welcome to pyupload</h1>
            <p class="lead">Development environment is successfully established.</p>
            <ul>
                <li>API Docs: <a href="/docs" target="_blank">/docs</a></li>
                <li>Adminer (DB): <a href="http://{adminer_host}:{adminer_port}" target="_blank">http://{adminer_host}:{adminer_port}</a></li>
                <li>App UI: <a href="/ui" target="_blank">/ui</a></li>
            </ul>
        </body>
    </html>
    """

