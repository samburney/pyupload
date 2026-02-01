import re
import html
import humanize

from pathlib import Path
from datetime import datetime, timezone
from uuid import uuid4
from markdown import markdown


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


def sanitised_markdown(text: str) -> str:
    """Sanitise markdown by escaping HTML entities and converting to HTML."""

    # Filter text through HTML entities santisier
    sanitised_text = html.escape(text)

    # Convert markdown to HTML
    return markdown(sanitised_text)


def time_ago(dt: datetime) -> str:
    """Return a human-readable time ago string."""
    return humanize.naturaltime(dt)


def sanitise_filename(filename: str) -> str | None:
    """Sanitize a filename to prevent directory traversal and other attacks.
    
    Removes path separators, null bytes, and control characters.
    Returns a safe filename suitable for use in Content-Disposition headers.
    
    Args:
        filename: The filename to sanitize
        
    Returns:
        A sanitized filename safe for file serving, or None if invalid
        
    Examples:
        >>> sanitise_filename("../../etc/passwd")
        'passwd'
        >>> sanitise_filename("file\x00name.txt")
        'filename.txt'
        >>> sanitise_filename("normal-file_123.jpg")
        'normal-file_123.jpg'
    """
    
    # Remove null bytes
    filename = filename.replace('\0', '')
    
    # Normalize path separators (replace backslashes with forward slashes)
    # This ensures Windows paths work correctly on Unix systems
    filename = filename.replace('\\', '/')
    
    # Get basename to prevent directory traversal (removes any path separators)
    filename = Path(filename).name
    
    # Remove control characters (ASCII 0-31 and 127)
    filename = re.sub(r'[\x00-\x1f\x7f]', '', filename)
    
    # Return None if empty after sanitization or if it's a parent directory reference
    if not filename or filename.strip() == '' or filename == '..':
        return None
        
    return filename
