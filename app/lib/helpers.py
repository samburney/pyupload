def is_bool(value: str | int | bool = False) -> bool:
    """Return a boolean from an boolean-like string."""

    return str(value).strip().lower() in {"1", "true", "yes", "on"}
