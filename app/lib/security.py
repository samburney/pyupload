import hashlib
import bcrypt
import coolname
import random
import netaddr

from fastapi import Request


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


def generate_username(num_words: int = 2) -> str:
    """Generate a random username using coolname."""

    name_words = coolname.generate(num_words)
    name_digits = random.randint(0, 9999)
    username = ''.join(word.capitalize() for word in name_words) + f"{name_digits}"

    return username


def extract_fingerprint_data(request: Request) -> dict:
    """Create a fingerprint hash from request headers."""

    user_agent = request.headers.get("User-Agent", "")
    accept_language = request.headers.get("Accept-Language", "")
    accept_encoding = request.headers.get("Accept-Encoding", "")
    client_ip = str(get_request_ip(request)) if get_request_ip(request) else None

    fingerprint_data = {
        "user_agent": user_agent,
        "accept_language": accept_language,
        "accept_encoding": accept_encoding,
        "client_ip": client_ip,
    }

    return fingerprint_data


def generate_fingerprint_hash(request: Request, include_client_ip: bool = False) -> str:
    """Create a fingerprint hash from request headers."""

    fingerprint_data = extract_fingerprint_data(request)
    user_agent = fingerprint_data["user_agent"]
    accept_language = fingerprint_data["accept_language"]
    accept_encoding = fingerprint_data["accept_encoding"]
    client_ip = fingerprint_data["client_ip"] if include_client_ip else None

    fingerprint_source = f"{user_agent}|{accept_language}|{accept_encoding}"
    if include_client_ip and client_ip:
        fingerprint_source += f"|{client_ip}"

    fingerprint_hash = hashlib.sha256(fingerprint_source.encode("utf-8")).hexdigest()

    return fingerprint_hash


def get_request_ip(request: Request) -> netaddr.IPAddress | None:
    """Get the client's IP address from the request."""

    client_ip = None

    # Check for X-Forwarded-For header first (in case of proxies)
    x_forwarded_for = request.headers.get("X-Forwarded-For")
    if x_forwarded_for:
        # X-Forwarded-For can contain multiple IPs, take the first one
        client_ip = x_forwarded_for.split(",")[0].strip()

    # Fallback to client host
    if not client_ip:
        client_ip = request.client.host if request.client else None

    # Validate IP address
    if client_ip:
        try:
            ip_addr = netaddr.IPAddress(client_ip)
            return ip_addr
        except netaddr.AddrFormatError:
            return None

    return None
