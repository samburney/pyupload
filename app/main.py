from app.models import init_db
import uvicorn

from pathlib import Path
from contextlib import asynccontextmanager
from collections.abc import AsyncGenerator
from urllib.parse import urlencode
from fastapi import FastAPI, Request, status
from fastapi.responses import RedirectResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.exceptions import RequestValidationError
from fastapi.encoders import jsonable_encoder
from starlette.middleware.sessions import SessionMiddleware
from starlette.exceptions import HTTPException as StarletteHTTPException

from app.lib.config import get_app_config
from app.lib.scheduler import scheduler
from app.lib.auth import delete_token_cookies
from app.lib.error_handling import NotAuthorisedError, ImageInvalidError, ImageProcessingError

from app.middleware.token_refresh import TokenRefreshMiddleware
from app.middleware.fingerprint_auto_login import FingerprintAutoLoginMiddleware

from app.ui.common.templating import templates
from app.ui.common.responses import error_template_response, error_response_for_get
from app.ui.common.security import LoginRequiredException

from app import api
from app import ui


config = get_app_config()


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    # App startup
    # Initialize Tortoise ORM - use as async context manager
    async with init_db():

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
# Fingerprint auto-login middleware
app.add_middleware(FingerprintAutoLoginMiddleware)

# Token refresh middleware
app.add_middleware(TokenRefreshMiddleware)

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
app.include_router(api.files.router, prefix='/api/v1')
app.include_router(api.images.router, prefix='/api/v1')
app.include_router(api.uploads.router, prefix='/api/v1')

# UI routes
app.include_router(ui.main.router, include_in_schema=False)
app.include_router(ui.archives.router, include_in_schema=False)
app.include_router(ui.auth.router, include_in_schema=False)
app.include_router(ui.collections.router, include_in_schema=False)
app.include_router(ui.gallery.router, include_in_schema=False)
app.include_router(ui.images.router, include_in_schema=False)
app.include_router(ui.tags.router, include_in_schema=False)
app.include_router(ui.uploads.router, include_in_schema=False)
app.include_router(ui.users.router, include_in_schema=False)


# Exception handlers
async def _route_error_response(request: Request, error_title: str, error_message: str, status_code: int) -> Response:
    """Route error responses to JSON, image error, or HTML based on the request path."""
    if request.url.path.startswith("/api/"):
        return JSONResponse(status_code=status_code, content={"detail": error_message})

    if request.url.path.startswith(("/get/", "/download/")):
        filename = Path(request.url.path).name
        return await error_response_for_get(
            filename=filename,
            error_title=error_title,
            error_message=error_message,
            status_code=status_code,
            request=request,
        )

    return await error_template_response(request, [error_message], status_code=status_code)


@app.exception_handler(StarletteHTTPException)
async def http_exception_handler(request: Request, exc: StarletteHTTPException):
    """Handle generic HTTP exceptions with custom error pages for UI routes."""

    # Skip for API endpoints
    if not request.url.path.startswith("/api/"):

        # Render HTML error pages for common error codes on UI routes
        if exc.status_code in (404, 405):
            return await error_template_response(request=request, status_code=exc.status_code, title=f"Error: {exc.status_code}", error_messages=[str(exc.detail)])

    # Return default response for everything else
    return JSONResponse(
        status_code=exc.status_code,
        content=jsonable_encoder({"detail": exc.detail}),
    )


@app.exception_handler(RequestValidationError)
async def validation_exception_handler(request: Request, exc: RequestValidationError):
    """Override default RequestValidationError handler to render UI error pages."""
    # Default handler for API endpoints
    if request.url.path.startswith("/api/"):
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
            content=jsonable_encoder({"detail": exc.errors()}),
        )

    # Handle specified, but empty `download` param on /get/ routes
    if request.url.path.startswith("/get/") and 'download' in request.query_params and request.query_params['download'] == '':
        query_params = dict(request.query_params)
        query_params['download'] = '1'
        return RedirectResponse(url=f'{request.url.path}?{urlencode(query_params)}', status_code=307)

    # For /get/ and /download/ the error may be rendered inside an image — single message only
    if request.url.path.startswith(("/get/", "/download/")):
        error_message = exc.errors()[0]['msg'] if exc.errors() else "An unknown error occurred while processing your request."
        return await _route_error_response(request, "Error 422: Unprocessable Content", error_message, 422)

    # For all other UI paths, surface all validation messages
    error_messages = [e['msg'] for e in exc.errors()] if exc.errors() else ["An unknown error occurred while processing your request."]
    return await error_template_response(request, error_messages, status_code=422)


@app.exception_handler(LoginRequiredException)
async def login_required_exception_handler(request: Request, exc: LoginRequiredException):
    ui.common.session.flash_message(request, "Please log in to access this page.", "error")

    # Remove invalid cookies and redirect to login page
    response = RedirectResponse(url="/login", status_code=303)
    delete_token_cookies(response)

    return response


@app.exception_handler(NotAuthorisedError)
async def not_authorised_exception_handler(request: Request, exc: NotAuthorisedError):
    return await _route_error_response(request, "Error 403: Unauthorized", str(exc), 403)


@app.exception_handler(FileNotFoundError)
async def file_not_found_exception_handler(request: Request, exc: FileNotFoundError):
    return await _route_error_response(request, "Error 404: Not Found", str(exc), 404)


@app.exception_handler(ImageInvalidError)
async def image_invalid_exception_handler(request: Request, exc: ImageInvalidError):
    return await _route_error_response(request, "Error 422: Unprocessable Content", str(exc), 422)


@app.exception_handler(ImageProcessingError)
async def image_processing_exception_handler(request: Request, exc: ImageProcessingError):
    return await _route_error_response(request, "Error 422: Unprocessable Content", str(exc), 422)


@app.exception_handler(ValueError)
async def value_error_exception_handler(request: Request, exc: ValueError):
    return await _route_error_response(request, "Error 400: Bad Request", str(exc), 400)


# Run the application server
if __name__ == "__main__":
    uvicorn.run(
        'app.main:app',
        host=config.app_host,
        port=config.app_port,
        reload=config.app_reload
    )
