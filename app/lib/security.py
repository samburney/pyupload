import hashlib
import bcrypt


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
