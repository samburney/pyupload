from fastapi import FastAPI
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.lib.config import get_app_config

from app import ui


app_config = get_app_config()

app = FastAPI(title="pyupload")

adminer_host = 'localhost' if '0.0.0.0' == app_config.adminer_host else app_config.adminer_host
adminer_port = app_config.adminer_port

app.mount("/static", StaticFiles(directory="app/static"), name="static")
app.include_router(ui.main.router)


@app.get("/", response_class=HTMLResponse)
async def read_root():
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
            </ul>
        </body>
    </html>
    """

