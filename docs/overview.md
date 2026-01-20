## pyupload

### Application overview

The purpose of this application is to serve as a modern replacement for `simplegallery`, an aging PHP/Laravel based file and image gallery application. `pyupload` aims to provide a semi-anonymous file, image, and video storage service, maintaining the core functionality of its predecessor while leveraging modern Python frameworks.

Initially, `pyupload` will adopt the underlying database and filesystem structure of `simplegallery` to ensure a smooth transition and maintain compatibility with existing data, while providing a foundation for future enhancements.

### Basic project technical specifications

The following technologies have been selected for `pyupload` to ensure a modern, testable, and maintainable codebase:

| Component            | Selected Technology           |
| -------------------- | ----------------------------- |
| Programming language | Python 3.13                   |
| Web/API framework    | FastAPI                       |
| Front-end Strategy   | HTMX + Jinja2 + Bootstrap 5   |
| Database backend     | MariaDB 11.8.x                |
| Database ORM         | Tortoise ORM                  |
| Template engine      | Jinja2                        |

### Feature Parity Goals

`pyupload` intends to replicate and improve upon the core features of `simplegallery`:

1.  **Anonymous & Authenticated Uploads**: Support for image, video, and general file uploads.
2.  **Gallery/Collection Management**: Organization of uploads into shareable collections.
3.  **Tagging System**: Categorization of content via tags.
4.  **Search Functionality**: Indexing and searching for uploaded content.
5.  **Direct Access & View Pages**: Providing both direct links to files and formatted "view" pages with metadata.
6.  **Legacy Integration**: Direct compatibility with the existing `simplegallery` database schema and file storage layout.

### Authentication & User System

`pyupload` implements a three-tier user system to balance ease of access with security:

1. **Anonymous Users**: Truly anonymous browsing with no database record. Limited to viewing public content.

2. **Unregistered Auto-Generated Accounts**: Created automatically via server-side fingerprinting (User-Agent, Accept headers, without IP to allow network changes). Users receive a Reddit-style auto-generated username (e.g., "HappyPanda1234") and JWT authentication. Fingerprint-based auto-login allows returning users to access their account seamlessly. These accounts have tiered upload restrictions and are marked abandoned after 90 days of inactivity (configurable via `UNREGISTERED_ACCOUNT_ABANDONMENT_DAYS`).

3. **Registered Accounts**: Full accounts with email/password authentication. Unregistered users can upgrade to registered status via the `/register` page, which clears their fingerprint and issues fresh tokens. Registered accounts have no upload restrictions and are never abandoned.

**Configuration**: Upload limits, allowed file types, and abandonment policy are configurable via environment variables (see `.env.example`). Fingerprints are cleared upon abandonment, allowing reuse on the same device.

**Security**: JWT tokens with refresh token rotation. Abandoned/disabled users cannot authenticate. API access restricted to registered users only (future feature).

### Roadmap

This roadmap outlines the milestones for the initial development phase.

#### v0.1 Preliminary Planning & Setup

1.  **Core Feature Design**: Define core business logic and file processing workflows in a framework-agnostic library layer.
2.  **Environment Configuration**: Establish `.env` based configuration.
3.  **Dockerization**: Create Docker Compose definitions for development (Database, App).
4.  **Legacy Schema Mapping**: Document and implement models mapping to the `simplegallery` database.
5.  **Basic Upload & View**: Implement core upload functionality and file viewing.
6.  **Documentation**:
    - Project README.
    - API documentation.
    - Migration/Transition guide from `simplegallery`.
