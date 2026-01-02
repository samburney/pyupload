# Tech Stack Options & Comparison

This document evaluates several framework options for `pyupload` based on the priorities of clean code, backend/frontend separation, and implementation simplicity.

## 1. Backend / API Frameworks

| Framework | Pros | Cons |
| :--- | :--- | :--- |
| **FastAPI** | Extremely fast, built-in async support, automatic API documentation (Swagger/OpenAPI), minimal boilerplate, strong type safety with Pydantic. | Newer than Flask, requires an ASGI server (Uvicorn). |
| **Flask** | Very simple, "micro" framework with a long history, huge ecosystem of extensions. | Synchronous by default (limiting for high-concurrency file handling), requires extra extensions for things that FastAPI provides natively (validation, docs). |

## 2. Database ORM

| ORM | Pros | Cons |
| :--- | :--- | :--- |
| **Tortoise ORM** | Async by design, clean Django-inspired API, excellent for FastAPI integration. | Lighter ecosystem than SQLAlchemy. |
| **Peewee** | Incredibly simple and lightweight, very easy to read, perfect for small-to-medium projects. | Synchronous, might feel limiting if the app scales significantly in complexity. |
| **SQLAlchemy**| Industry standard, incredibly powerful. | High learning curve, very verbose (high boilerplate), complex async implementation. |

## 3. Frontend & UI Strategy

| Approach | Pros | Cons |
| :--- | :--- | :--- |
| **FastAPI + Jinja2 + Vanilla JS/Bootstrap** | Clean separation of concerns, leverages existing familiarity with Bootstrap, no complex build steps/Node.js required. | Requires manual JavaScript for dynamic elements (e.g., upload progress bars). |
| **NiceGUI** | High-level Python-only UI development, very rapid prototyping, built-in components. | Can blur the line between backend and frontend logic; may not feel like "true" separation if you want a decoupled API. |
| **FastAPI + HTMX** | Provides a modern reactive feel without a heavy JS framework; logic stays in Python but with clean HTML-based interactions. | Newer paradigm that requires a mental shift in how "frontend" handles data. |

## 4. Key Priorities Assessment

### Priority 1: Backend/Frontend Separation
- **FastAPI** is the winner here. It is built from the ground up to be an API-first framework. Even when used with templates, the separation between data validation (Pydantic) and presentation (Jinja2/JS) is very distinct.

### Priority 2: Implementation Simplicity (Minimal Boilerplate)
- **FastAPI + Tortoise ORM** offers significantly less boilerplate than Laravel or even Flask + SQLAlchemy. You define models, and the ORM handles the rest without complex configuration.

### Priority 3: Testable Logical Parts
- The **FastAPI/Tortoise** stack allows for easy dependency injection and isolated testing of API endpoints, business logic, and database interactions.
