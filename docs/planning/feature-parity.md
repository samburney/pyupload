# Feature Parity Requirements

This document outlines the features and functionalities of `simplegallery` that must be implemented in `pyupload` to achieve initial feature parity.

## 1. Data Model (Legacy Compatibility)

`pyupload` must support the existing `simplegallery` database schema to allow for a seamless transition.

### Core Entities
- **Users**: Authentication and ownership.
- **Uploads**: Core file metadata (original name, clean name, system name, extension, size, type, viewed count, private status).
- **Images**: Extended metadata for image files (width, height, bits, channels).
- **Collections**: User-defined groups of uploads.
- **Tags**: Global categorization of uploads.

## 2. File Storage & Handling

### Storage Structure
- Files are stored in a flat directory system (`public/files`).
- System names are used for the actual files to avoid collisions and preserve the original filename in metadata.

### Processing & Conversions
- **Dynamic Resizing**: Support for on-the-fly resizing via URLs (e.g., `view/123/filename-thumb.jpg`).
- **Format Conversion**: Delivery of files in different formats if requested by extension.
- **Image Rotation**: Server-side rotation of images, updating metadata (width/height) and clearing caches.
- **View Counting**: Incrementing the `viewed` metric upon file delivery.

## 3. User Interface

### Global Navigation
- **Home**: Latest public uploads gallery.
- **Random**: A selection of random public uploads.
- **Popular**: Most viewed public uploads.
- **Tags/Collections**: Dedicated landing pages for browsing by category.
- **Search**: Keyword search across titles, descriptions, and tags.

### Key Workflows
- **Uploading**:
    - Sidebar-based "Drop or Paste" zone available globally.
    - Support for multiple file uploads.
    - Progress tracking.
- **Viewing**:
    - Detailed view page for individual uploads.
    - Metadata display (Size, Dimensions, Type).
    - Social/Direct link sharing options.
    - Inline editing for Tags and Title/Description (for owners).
    - Privacy toggle (Private/Public).
- **Management**:
    - "Your Uploads" and "Your Collections" for logged-in users.
    - Delete functionality for owners/admins.

## 4. Access Control

- **Semi-Anonymous**: Support for anonymous browsing and viewing of public uploads.
- **Authenticated Features**: Uploading (if configured), managing personal collections, and setting files to private.
- **Privacy**: `private` files are only visible to the owner.

## 5. Preliminary Implementation Notes

### Candidate Python Tech Stack (Research Ongoing)
- **API**: FastAPI (for modern, async-ready REST endpoints).
- **UI**: NiceGUI or React (to provide a responsive, dynamic experience similar to the original).
- **Processing**: Pillow (Python Imaging Library) for image transformations.
- **Database**: SQLAlchemy or Tortoise ORM mapping to MariaDB.
