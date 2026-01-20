import re


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
    mime_pattern = re.compile(r'^[a-zA-Z0-9][a-zA-Z0-9!#$&\-\^_+.]*\/[a-zA-Z0-9][a-zA-Z0-9!#$&\-\^_+.]*$')
    
    for mime_type in mime_string.split(','):
        mime_type = mime_type.strip()
        if not mime_pattern.match(mime_type):
            return False
    return True
