from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from starlette.middleware.sessions import SessionMiddleware

from app.lib.config import get_app_config

from app.models import init_db

from app import ui


app_config = get_app_config()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # App startup
    # Initialize Tortoise ORM
    await init_db()


    # App running
    yield

    # App shutdown
    # App cleanup code can be added here if needed


# Init FastAPI app
app = FastAPI(
    title="pyupload",
    lifespan=lifespan,
)

# Middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=app_config.session_secret_key,
    session_cookie="pyupload_session",
    max_age=app_config.session_max_age_days * 24 * 60 * 60,  # days to seconds
    path=app_config.session_file_path,
)

# App routes
# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# UI routes
app.include_router(ui.main.router)
app.include_router(ui.auth.router)


# Development environment links
@app.get("/", response_class=HTMLResponse)
async def read_root():
    adminer_host = 'localhost' if '0.0.0.0' == app_config.adminer_host else app_config.adminer_host
    adminer_port = app_config.adminer_port
    
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

