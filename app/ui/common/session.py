from fastapi import Request


def flash_message(request: Request, message: str, message_type: str = "info") -> None:
    """Store a flash message in the session."""
    if "_flashes" not in request.session:
        request.session["_flashes"] = []

    request.session["_flashes"].append({
        "message": message,
        "message_type": message_type,
    })


def get_flashed_messages(request: Request) -> tuple[list[str], list[str]]:
    """Retrieve and clear flashed messages from the session."""
    info_messages = []
    error_messages = []

    messages = request.session.pop("_flashes", []) if "_flashes" in request.session else []

    while len(messages) > 0:
        message = messages.pop()
        if message["message_type"] == "error":
            error_messages.append(message["message"])
        else:
            info_messages.append(message["message"])

    return info_messages, error_messages
