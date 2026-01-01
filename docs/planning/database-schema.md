# Database Schema (Legacy)

This document describes the existing `simplegallery` database schema that `pyupload` will initially adopt.

## Tables

### `users`
Stores user accounts for authentication and ownership.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT (PK) | Auto-increment |
| `username` | VARCHAR(64) | |
| `email` | VARCHAR(255) | |
| `password` | VARCHAR(60) | Bcrypt hash |
| `remember_token` | VARCHAR(100) | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `uploads`
The central table for all uploaded files.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT (PK) | |
| `user_id` | INT | FK to `users` |
| `filegroup_id`| INT | Default 0 |
| `description` | VARCHAR(255) | |
| `name` | VARCHAR(255) | System name on disk (no ext) |
| `cleanname` | VARCHAR(255) | SEO friendly name |
| `originalname`| VARCHAR(255) | |
| `ext` | VARCHAR(10) | File extension |
| `size` | INT UNSIGNED | In bytes |
| `type` | VARCHAR(255) | MIME type |
| `viewed` | INT UNSIGNED | View count |
| `private` | BOOLEAN | |
| `extra` | VARCHAR(32) | Hints for processing (e.g. 'image') |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `images`
Extended metadata for files where `extra` = 'image'.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT (PK) | |
| `upload_id` | INT | FK to `uploads` |
| `type` | VARCHAR(255) | Image format (e.g. 'jpeg') |
| `width` | INT | |
| `height` | INT | |
| `bits` | INT | |
| `channels` | INT | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `collections`
Groups of uploads created by users.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT (PK) | |
| `user_id` | INT | FK to `users` |
| `name` | VARCHAR(255) | Display name |
| `name_unique` | VARCHAR(255) | Slug for URLs |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### `tags`
Global tags for categorization.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT (PK) | |
| `name` | VARCHAR(255) | |
| `created_at` | TIMESTAMP | |
| `updated_at` | TIMESTAMP | |

### Pivot Tables
- **`collection_upload`**: Links `collections` to `uploads`.
- **`tag_upload`**: Links `tags` to `uploads`.

## Implementation Strategy
`pyupload` will use an ORM to map these tables. While some field names might be modernized in the models, the underlying database structure must remain compatible to allow both applications to run against the same data if necessary during the transition.
