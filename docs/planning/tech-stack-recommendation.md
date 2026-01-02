# Tech Stack Recommendation (Finalized)

Based on the research and project priorities, the following stack has been selected for `pyupload`. A key architectural principle will be the strict separation of **Core Business Logic** from the **Delivery Layer** (API and UI).

## Recommended Stack

| Component | Technology | Rationale |
| :--- | :--- | :--- |
| **Backend Framework** | **FastAPI** | Selected for its speed, modern async features, and minimal boilerplate. It will be used primarily as an asynchronous delivery layer. |
| **ORM** | **Tortoise ORM** | Provides an async, Django-like API that maps cleanly to the legacy MariaDB schema. |
| **Database** | **MariaDB** | Required for legacy compatibility with `simplegallery`. |
| **Frontend Strategy** | **FastAPI + HTMX + Jinja2** | Combines standard HTML templates with HTMX for interactivity, avoiding the complexity and persistent connection requirements of WebSockets or heavy JS frameworks. |
| **Image Processing** | **Pillow** | Standard library for handling rotation, resizing, and metadata, encapsulated within the core business logic. |
| **Validation** | **Pydantic** | Used to enforce data integrity across both the core logic and the API layer. |

## Rationale vs. Priorities

### 1. Backend/Frontend Separation
Using **FastAPI** with **Jinja2** templates and **HTMX** allows you to serve HTML while keeping the API endpoints clean. HTMX requests are essentially AJAX calls that return HTML fragments, which keeps the "dynamic" logic isolated to specific endpoints. If you later decide to go with a full JS frontend (e.g., React), the FastAPI backend is already "REST-ready."

### 2. Implementation Simplicity
This stack avoids the "magic" of Laraval and the verbosity of Django. You only write the code you need. Tortoise ORM's syntax is very similar to the Django models you might be familiar with, but without the baggage of the rest of the framework.

### 3. Logical Breakdown and Testing
FastAPI's built-in `TestClient` (based on Starlette/HTTPX) allows you to test endpoints in isolation. Tortoise ORM's `DBConfig` makes it easy to swap the MariaDB backend for a fast, in-memory SQLite database for unit testing.

## Next Steps
1.  Initialize the project structure with a focus on logical separation:
    - `app/lib/`: Core business logic and file processing (framework-agnostic).
    - `app/models/`: Tortoise ORM database models.
    - `app/api/`: FastAPI REST endpoints (Delivery Layer).
    - `app/ui/`: FastAPI/HTMX views and Jinja2 templates (Delivery Layer).
    - `app/templates/`: Jinja2 base templates and fragments.
    - `app/static/`: CSS and static assets.
2.  Set up `docker-compose.yml` with MariaDB and the Python environment.
3.  Implement legacy database mapping in Tortoise ORM.
4.  Develop core business logic for file handling in `app/lib/` before implementing UI logic.
