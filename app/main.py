import uvicorn

from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from urllib.parse import urlencode
from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.middleware.sessions import SessionMiddleware

from app.lib.config import get_app_config
from app.lib.scheduler import scheduler
from app.middleware.token_refresh import TokenRefreshMiddleware
from app.middleware.fingerprint_auto_login import FingerprintAutoLoginMiddleware

from app.models import init_db

from app.ui.common.security import LoginRequiredException

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

# Middleware - Note: Applied to request in reverse order
# Token refresh middleware
app.add_middleware(TokenRefreshMiddleware)

# Fingerprint auto-login middleware
app.add_middleware(FingerprintAutoLoginMiddleware)

# Session middleware
app.add_middleware(
    SessionMiddleware,
    secret_key=config.auth_token_secret_key,
    session_cookie="pyupload_session",
    max_age=24 * 60 * 60,  # days to seconds
    path="/",  # Cookie path - should be "/" for site-wide access
)

# App routes
# Static files
app.mount("/static", StaticFiles(directory="app/static"), name="static")

# API routes
app.include_router(api.auth.router, prefix='/api/v1')
app.include_router(api.uploads.router, prefix='/api/v1')

# UI routes
app.include_router(ui.main.router, include_in_schema=False)
app.include_router(ui.auth.router, include_in_schema=False)
app.include_router(ui.uploads.router, include_in_schema=False)
app.include_router(ui.users.router, include_in_schema=False)


# Exception handlers
@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Override default RequestValidationError handler to render UI error pages."""
    # Default handler for API endpoints
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=jsonable_encoder({"detail": exc.errors()}),
        )

    elif request.url.path.startswith("/get/"):
        # Handle specified, but empty `download` param
        if 'download' in request.query_params and request.query_params['download'] == '':
            query_params = dict(request.query_params)
            query_params['download'] = '1'

            url = f'{request.url.path}?{urlencode(query_params)}'
            response = RedirectResponse(url=url, status_code=307)
            return response

    # HTTPException handler for UI endpoints
    error_messages = []
    for error in exc.errors():
        error_messages.append(f"{error['type'].capitalize()}: {error['msg']} - {error['loc'][-1]}")

    return ui.common.error_response(request, error_messages, status_code=422)


@app.exception_handler(LoginRequiredException)
async def login_required_exception_handler(request: Request, exc: LoginRequiredException):
    ui.common.session.flash_message(request, "Please log in to access this page.", "error")
    return RedirectResponse(url="/login", status_code=303)


# Run the application server
if __name__ == "__main__":
    uvicorn.run(
        'app.main:app',
        host=config.app_host,
        port=config.app_port,
        reload=config.app_reload
    )
