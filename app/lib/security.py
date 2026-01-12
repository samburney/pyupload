import hashlib
import bcrypt
import base64


def hash_password(password: str) -> str:
    """Hash a plaintext password using bcrypt.
    
    Uses SHA256 to hash the password first, allowing support for passwords
    longer than bcrypt's 72-byte limit while maintaining compatibility with
    existing bcrypt hashes.
    """
    # SHA256 hash the password to support arbitrary lengths
    password_hash = hashlib.sha256(password.encode('utf-8')).digest()
    salt = bcrypt.gensalt()
    return bcrypt.hashpw(password_hash, salt).decode('utf-8')


def verify_password(plain_password: str, hashed_password: str) -> bool:
    """Verify a plaintext password against a hashed password.
    
    Supports both legacy bcrypt hashes (from Laravel) and new SHA256-bcrypt
    hashes, automatically detecting the format.
    """
    plain_password_hash = hashlib.sha256(plain_password.encode('utf-8')).digest()
    hashed_password_bytes = hashed_password.encode('utf-8')
    return bcrypt.checkpw(plain_password_hash, hashed_password_bytes)


def session_hash(user_id: int, secret_key: str) -> str:
    """Generate a session hash for a user based on their ID and a secret key."""
    hash_input = f"{user_id}:{secret_key}".encode('utf-8')
    return hashlib.sha256(hash_input).hexdigest()


def session_encode(user_id: int, secret_key: str) -> str:
    """Encode user ID and session hash into a base64 string for session storage."""
    user_hash = session_hash(
        user_id=user_id,
        secret_key=secret_key,
    )
    user_encode = base64.b64encode(f"{user_id}:{user_hash}".encode()).decode()
    return user_encode


def session_decode(session_value: str) -> None | tuple[int, str]:
    """Decode a base64 session value into user ID and hash."""
    try:
        decoded = base64.b64decode(session_value).decode()
        user_id_str, user_hash = decoded.split(":", 1)
        user_id = int(user_id_str)
        return user_id, user_hash
    except (ValueError):
        return None


def authenticate_session(session_value: str, secret_key: str) -> bool:
    """Authenticate a session value against the expected hash."""
    if session_decode is not None:
        user_id, user_hash = session_decode(session_value) # type: ignore
    else:
        return False

    expected_hash = session_hash(
        user_id=user_id,
        secret_key=secret_key,
    )

    return user_hash == expected_hash


def authenticated_user_id(session_value: str, secret_key: str) -> None | int:
    """Return the authenticated user ID from a session value, or None if invalid."""
    if authenticate_session(session_value, secret_key):
        decoded = session_decode(session_value)
        if decoded is not None:
            user_id, _ = decoded
            return user_id
    return None
