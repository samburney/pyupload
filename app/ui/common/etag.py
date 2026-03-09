import hashlib
from fastapi import Request
from fastapi.responses import Response

from app.models.uploads import UploadSerializer
from app.models.common.pagination import PaginationParams


def get_paginated_gallery_etag(
    *,
    uploads: list[UploadSerializer],
    pagination: PaginationParams,
    user_id: int | None,
    etag_prefix: str = "gallery"
) -> str:
    """Build a weak ETag for paginated gallery content.

    Generates a hash-based ETag that changes whenever:
    - The user context changes
    - Pagination parameters change
    - Upload data changes (id or updated_at)
    """
    signature_parts = [
        str(user_id or 0),
        str(pagination.page),
        str(pagination.page_size),
        str(pagination.count),
    ]

    for upload in uploads:
        updated_at = upload.updated_at.isoformat() if upload.updated_at else ""
        signature_parts.append(f"{upload.id}:{updated_at}")

    digest = hashlib.sha1("|".join(signature_parts).encode("utf-8")).hexdigest()
    return f'W/"{etag_prefix}-{digest}"'


def get_cache_headers(*, etag: str) -> dict[str, str]:
    """Build cache control headers for a response with ETag support.

    Returns headers for:
    - Cache-Control: private, max-age=60, must-revalidate
    - ETag: <etag value>
    - Vary: Cookie (since cache varies by user)
    """
    return {
        "Cache-Control": "private, max-age=60, must-revalidate",
        "ETag": etag,
        "Vary": "Cookie",
    }


def check_etag_and_return_304_if_match(
    request: Request,
    etag: str,
) -> Response | None:
    """Check If-None-Match header and return 304 response if ETag matches.

    Returns a 304 Not Modified response if the client's ETag matches,
    otherwise returns None to continue with normal response.
    """
    if_none_match = request.headers.get("if-none-match")
    if not if_none_match:
        return None

    etag_values = [value.strip() for value in if_none_match.split(",")]
    if etag in etag_values or "*" in etag_values:
        return Response(
            status_code=304,
            headers=get_cache_headers(etag=etag)
        )

    return None
