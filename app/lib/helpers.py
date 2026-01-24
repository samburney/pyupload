import re
from datetime import datetime, timezone
from uuid import uuid4


# RFC 6838 MIME type pattern: type/subtype
MIME_TYPE_PATTERN = r'^[a-zA-Z0-9][a-zA-Z0-9!#$&\-\^_+.]*\/[a-zA-Z0-9][a-zA-Z0-9!#$&\-\^_+.]*$'

# Well known multi-part file extensions
MULTIPART_EXTENSIONS = {
    '.tar.gz': 'application/gzip',
    '.tar.bz2': 'application/x-bzip2',
    '.tar.xz': 'application/x-xz',
    '.tar.zstd': 'application/x-zstd',
}


def is_bool(value: str | int | bool = False) -> bool:
    """Return a boolean from an boolean-like string."""

    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def validate_mime_types(mime_string: str) -> bool:
    """Validate comma-separated MIME types or '*' wildcard.
    
    Args:
        mime_string: Comma-separated MIME types (e.g., "image/jpeg,image/png") or "*"
        
    Returns:
        True if valid, False otherwise
        
    Examples:
        >>> validate_mime_types("*")
        True
        >>> validate_mime_types("image/jpeg,image/png")
        True
        >>> validate_mime_types("invalid")
        False
    """
    if not mime_string or not mime_string.strip():
        return False
        
    if mime_string.strip() == "*":
        return True
    
    # RFC 6838 MIME type pattern: type/subtype
    # type and subtype must start with alphanumeric and can contain limited special chars
    mime_pattern = re.compile(MIME_TYPE_PATTERN)
    
    for mime_type in mime_string.split(','):
        mime_type = mime_type.strip()
        if not mime_pattern.match(mime_type):
            return False
    return True


def split_filename(filename: str) -> tuple[str, str]:
    """Split a filename into name and extension."""

    # Strip whitespace
    filename = filename.strip()

    # Check for well-known multi-part extensions
    for ext in MULTIPART_EXTENSIONS.keys():
        if filename.lower().endswith(ext):
            name = filename[:-len(ext)]
            return name, ext.lstrip('.')

    # Find extension in filename and return name and extension
    parts = filename.rsplit('.', 1)
    if len(parts) == 2:
        return parts[0], parts[1]
    
    # No extension found, return name and empty string
    return filename, ''


def make_clean_filename(filename: str) -> str:
    """Clean a filename by removing unsafe characters."""

    # Remove all characters except alphanumerics, and underscores
    clean_filename = re.sub(r'[^_a-z0-9]', '_', filename.lower())

    # Trim and remove duplicate underscores
    clean_filename = re.sub(r'__+', '_', clean_filename).strip('_')

    return clean_filename


def make_unique_filename(filename: str) -> str:
    """Generate a unique filename by appending datestamp and UUID."""

    clean_name = make_clean_filename(filename)

    datetime_stamp = datetime.now(timezone.utc).strftime(r'%Y%m%d-%H%M%S')
    unique_id = uuid4().hex[:8]
    unique_filename = f"{clean_name}_{datetime_stamp}_{unique_id}"

    return unique_filename
