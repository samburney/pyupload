from fastapi import Request


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


def get_flashed_messages(request: Request) -> tuple[list[str], list[str]]:
    """Retrieve and clear flashed messages from the session."""
    info_messages = []
    error_messages = []

    # Get messages from session and clear them by setting to empty list
    messages = request.session.get("_flashes", [])
    request.session["_flashes"] = []

    # Add to appropriate lists
    for message in messages:
        if message["message_type"] == "error":
            error_messages.append(message["message"])
        else:
            info_messages.append(message["message"])

    return info_messages, error_messages
