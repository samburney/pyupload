# Database Schema (Legacy)

This document describes the existing `simplegallery` database schema that `pyupload` will initially adopt. It is based on the actual production dump in [legacy-database-structure.sql](file:///Users/sam/code/pyupload/docs/planning/legacy-database-structure.sql).

## Tables

### `users`
Stores user accounts for authentication and ownership.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT(10) UNSIGNED (PK) | Auto-increment |
| `username` | VARCHAR(64) | |
| `email` | VARCHAR(255) | |
| `password` | VARCHAR(60) | |
| `created_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |
| `updated_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |
| `remember_token` | VARCHAR(100) | |

### `uploads`
The central table for all uploaded files.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT(10) UNSIGNED (PK) | Auto-increment |
| `user_id` | INT(11) | FK to `users` |
| `filegroup_id`| INT(11) | Default 0 |
| `description` | VARCHAR(255) | |
| `name` | VARCHAR(255) | System name on disk (no ext) |
| `cleanname` | VARCHAR(255) | SEO friendly name |
| `originalname`| VARCHAR(255) | |
| `ext` | VARCHAR(10) | File extension |
| `size` | INT(10) UNSIGNED | In bytes |
| `type` | VARCHAR(255) | MIME type |
| `extra` | VARCHAR(32) | Hints for processing (e.g. 'image') |
| `created_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |
| `updated_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |
| `viewed` | INT(10) UNSIGNED | Default 0 |
| `private` | TINYINT(1) | Default 0 |

### `images`
Extended metadata for files where `extra` = 'image'.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT(10) UNSIGNED (PK) | Auto-increment |
| `upload_id` | INT(11) | FK to `uploads` |
| `type` | VARCHAR(255) | Image format (e.g. 'jpeg') |
| `width` | INT(11) | |
| `height` | INT(11) | |
| `bits` | INT(11) | |
| `channels` | INT(11) | |
| `created_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |
| `updated_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |

### `collections`
Groups of uploads created by users.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT(10) UNSIGNED (PK) | Auto-increment |
| `user_id` | INT(11) | FK to `users` |
| `name` | VARCHAR(255) | Display name |
| `name_unique` | VARCHAR(255) | Slug for URLs |
| `created_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |
| `updated_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |

### `tags`
Global tags for categorization.
| Column | Type | Notes |
| :--- | :--- | :--- |
| `id` | INT(10) UNSIGNED (PK) | Auto-increment |
| `name` | VARCHAR(255) | |
| `created_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |
| `updated_at` | TIMESTAMP | Default '0000-00-00 00:00:00' |

### Pivot Tables
- **`collection_upload`**: `collection_id` (INT), `upload_id` (INT) - Links `collections` to `uploads`.
- **`tag_upload`**: `tag_id` (INT), `upload_id` (INT) - Links `tags` to `uploads`.

### `password_reminders`
- `email` (VARCHAR), `token` (VARCHAR), `created_at` (TIMESTAMP).

## Implementation Strategy
`pyupload` will use Tortoise ORM to map these tables. We must ensure that the `TIMESTAMP` fields with `0000-00-00 00:00:00` defaults are handled gracefully in Python (mapping to `None` or a minimum timestamp where appropriate).
