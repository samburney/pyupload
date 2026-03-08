import json

from fastapi import Request


# UI layout breakpoints and dimensions
BREAKPOINTS = {
    "xs": 0,
    "sm": 40 * 16,
    "md": 48 * 16,
    "lg": 64 * 16,
    "xl": 80 * 16,
    "2xl": 96 * 16,
    "3xl": 112 * 16,
    "4xl": 128 * 16,
    "5xl": 144 * 16,
}
BREAKPOINT_FRAME_PADDING = {
    "sm": 16,
}
BREAKPOINT_SIDEBAR_WIDTHS = {
    "xs": 0,
    "sm": 0 + 16,
    "md": 138 + 16,
    "lg": 240 + 16,
    "xl": 253 + 16,
    "2xl": 256 + 16,
    "3xl": 256 + 16,
    "4xl": 256 + 16,
}


def flash_message(request: Request, message: str, message_type: str = "info") -> None:
    """
        Store a flash message in the session.

        Args:
            request (Request): The incoming request object.
            message (str): The message to be flashed.
            message_type (str): The type of the message, e.g., "info" or "error".
    """

    # Get existing flashes or create new list
    flashes = request.session.get("_flashes", [])
    flashes.append({
        "message": message,
        "message_type": message_type,
    })
    
    # Reassign to trigger session modification tracking
    request.session["_flashes"] = flashes


def get_flashed_messages(request: Request) -> dict[str, list[str]]:
    """Retrieve and clear flashed messages from the session."""
    info_messages = []
    error_messages = []
    warning_messages = []

    # Get messages from session and clear them by setting to empty list
    messages = request.session.get("_flashes", [])
    request.session["_flashes"] = []

    # Add to appropriate lists
    for message in messages:
        if message["message_type"] == "error":
            error_messages.append(message["message"])
        elif message["message_type"] == "warning":
            warning_messages.append(message["message"])
        else:
            info_messages.append(message["message"])

    return {
        "info": info_messages,
        "error": error_messages,
        "warning": warning_messages,
    }


def get_client_dimensions(request: Request) -> dict[str, int] | None:
    """Get the client's viewport dimensions from the session."""

    client_width: int | None = None
    client_height: int | None = None
    client_breakpoint: str | None = None
    client_breakpoint_width: int | None = None

    # Handle client window sizing from request if we have it
    client_dimensions_json = request.cookies.get('window_dimensions', None)
    if client_dimensions_json:
        try:
            # Determine client dimensions from cookie
            client_dimensions = json.loads(client_dimensions_json)
            client_width = client_dimensions.get('window_width', None)
            client_height = client_dimensions.get('window_height', None)
        except json.JSONDecodeError:
            pass
    else:
        return None

    # Determine client breakpoint based on width
    if client_width is not None and client_height is not None:
        for breakpoint_name, breakpoint_width in BREAKPOINTS.items():
            if client_width >= breakpoint_width:
                client_breakpoint = breakpoint_name
                client_breakpoint_width = BREAKPOINTS[breakpoint_name]

    # Build client dimensions dict
    client_dimensions = {
        "width": client_width,
        "height": client_height,
        "breakpoint": client_breakpoint,
        "breakpoint_width": client_breakpoint_width,
    }

    return client_dimensions
