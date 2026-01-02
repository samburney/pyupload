# Tech Stack Recommendation

Based on the research and your specific priorities, the following stack is recommended for `pyupload`.

## Recommended Stack

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** | Provides the best balance of speed, modern async features, and minimal boilerplate. It enforces a clean separation of concerns via Pydantic schemas. |
| **ORM** | **Tortoise ORM** | Offers a clean, readable API that integrates seamlessly with FastAPI's async nature. It will map cleanly to the legacy MariaDB schema. |
| **Database** | **MariaDB** | Required for legacy compatibility with `simplegallery`. |
| **Frontend Strategy** | **FastAPI + Jinja2 + Bootstrap 5 + HTMX** | **Bootstrap 5** provides the familiar UI framework without the jQuery dependency of 4.x. **HTMX** allows for dynamic, modern features (like progress bars and tag editing) without the complexity of a JS framework like React, keeping logic in the backend while maintaining clear template separation. |
| **Image Processing** | **Pillow** | The standard Python library for handling the image rotation, resizing, and metadata requirements. |
| **Validation** | **Pydantic** | Native to FastAPI; ensures all data coming in and out is clean and well-documented. |

## Rationale vs. Priorities

### 1. Backend/Frontend Separation
Using **FastAPI** with **Jinja2** templates and **HTMX** allows you to serve HTML while keeping the API endpoints clean. HTMX requests are essentially AJAX calls that return HTML fragments, which keeps the "dynamic" logic isolated to specific endpoints. If you later decide to go with a full JS frontend (e.g., React), the FastAPI backend is already "REST-ready."

### 2. Implementation Simplicity
This stack avoids the "magic" of Laraval and the verbosity of Django. You only write the code you need. Tortoise ORM's syntax is very similar to the Django models you might be familiar with, but without the baggage of the rest of the framework.

### 3. Logical Breakdown and Testing
FastAPI's built-in `TestClient` (based on Starlette/HTTPX) allows you to test endpoints in isolation. Tortoise ORM's `DBConfig` makes it easy to swap the MariaDB backend for a fast, in-memory SQLite database for unit testing.

## Next Steps
1.  Initialize the project structure:
    - `app/api/` (Endpoints)
    - `app/models/` (Tortoise models)
    - `app/templates/` (Jinja2)
    - `app/static/` (CSS/JS)
2.  Set up `docker-compose.yml` with MariaDB and the Python app.
3.  Implement the legacy database mapping in Tortoise ORM.
